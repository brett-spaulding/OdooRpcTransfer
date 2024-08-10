import argparse
import json
import odoorpc
import os
from time import sleep
from dotenv import load_dotenv

load_dotenv()
ODOO_HOST_REMOTE = os.getenv('ODOO_HOST_REMOTE')
ODOO_PORT_REMOTE = os.getenv('ODOO_PORT_REMOTE')
ODOO_USER_REMOTE = os.getenv('ODOO_USER_REMOTE')
ODOO_PASS_REMOTE = os.getenv('ODOO_PASS_REMOTE')
ODOO_DB_REMOTE = os.getenv('ODOO_DB_REMOTE')
ODOO_HOST_LOCAL = os.getenv('ODOO_HOST_LOCAL')
ODOO_PORT_LOCAL = os.getenv('ODOO_PORT_LOCAL')
ODOO_USER_LOCAL = os.getenv('ODOO_USER_LOCAL')
ODOO_PASS_LOCAL = os.getenv('ODOO_PASS_LOCAL')
ODOO_DB_LOCAL = os.getenv('ODOO_DB_LOCAL')

parser = argparse.ArgumentParser(description='Save text to a file')
parser.add_argument('-m', '--model')
parser.add_argument('--pull', default=False, action='store_true')
parser.add_argument('--cache', default=True, action='store_true')
args = parser.parse_args()


def search_cache(model, record_id):
    data = {}
    cwd = os.getcwd()
    file_dir = os.path.join(cwd, 'models/%s/%s.json' % (model, record_id))
    if os.path.exists(file_dir):
        with open(file_dir, 'r') as f:
            data = json.load(f)
    return data


def record_error(model, error, record_id=False):
    cwd = os.getcwd()
    log_path = 'logs/error/%s/%s' % (model, record_id) if record_id else 'logs/error/%s/' % model
    logs_dir = os.path.join(cwd, log_path)
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    file_path = os.path.join(logs_dir, f"{model}.txt")
    with open(file_path, 'w') as f:
        f.write(str(error))
    return


def save_data(model, records):
    for record in records:
        cwd = os.getcwd()
        pages_dir = os.path.join(cwd, 'models/%s' % model)
        if not os.path.exists(pages_dir):
            os.makedirs(pages_dir)
        file_path = os.path.join(pages_dir, f"{record.get('id')}.json")

        with open(file_path, 'w') as f:
            f.write(json.dumps(record, indent=4))

    return


def setup(env='remote'):
    if env == 'remote':
        odoo = odoorpc.ODOO(ODOO_HOST_REMOTE, port=ODOO_PORT_REMOTE)
        odoo.login(ODOO_DB_REMOTE, ODOO_USER_REMOTE, ODOO_PASS_REMOTE)
    elif env == 'local':
        odoo = odoorpc.ODOO(ODOO_HOST_LOCAL, port=ODOO_PORT_LOCAL)
        odoo.login(ODOO_DB_LOCAL, ODOO_USER_LOCAL, ODOO_PASS_LOCAL)
    else:
        raise ValueError('env must be remote or local')
    return odoo


class OdooMigrator(object):
    def __init__(self):
        self.odoo = setup(env='remote') if args.pull else setup(env='local')
        self.model = args.model

    def get_record(self, model, record_id):
        """
        Return values for record.  Will search local cache first unless specified otherwise.  Save remote data locally.
        :param model: Dot notation of the model (ex. 'res.partner')
        :param record_id: Integer value of the record ID
        :return: Record object
        """
        values = {}
        record_id = int(record_id)
        if args.cache:
            values = search_cache(model, record_id)
        if not values:
            try:
                values = self.odoo.execute_kw(model, 'read', [[record_id]], {'fields': []})
                save_data(model, values)
                # Prevent too many requests error from Odoo
                sleep(2)
            except Exception as e:
                record_error(model, record_id, e)
        return values

    def get_model(self, model):
        """
        Will Sync model from remote locally.  Use --cache=False to update saved records.
        :param model: Dot notation of the model (ex. 'res.partner')
        :return: List of Record objects
        """
        record_set = []
        try:
            model_record_ids = self.odoo.env[model].search([])
            record_ids = self.odoo.env[model].browse(model_record_ids)
            print('=================')
            print('Model: %s' % model)
            print('-----------------')
            index = 0
            index_length = len(record_ids)
            for record_id in record_ids:
                index += 1
                print('Record: %s/%s' % (index, index_length))
                record_data = self.get_record(model, record_id)
                record_set.append(record_data)
        except Exception as e:
            record_error(model, e)

        return record_set

    def pull_model(self):
        """
        Pull model from Remote odoo instance
        :param model: Dot notation of the model (ex. 'res.partner')
        :return: True
        """
        print('Pulling Model: %s' % args.model)
        model = 'ir.model' if args.model == 'all' else args.model
        records = self.get_model(model)
        if args.model == 'all':
            for model in records:
                self.get_model(model.get('model')) if model.get('model') else False

        return True


if __name__ == '__main__':
    odoo = OdooMigrator()
    if args.pull:
        odoo.pull_model()
    elif args.push:
        pass
