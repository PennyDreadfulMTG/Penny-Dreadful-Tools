from decksite import database
from decksite.database import db
from shared import configuration


def setup_test_db():
    name = configuration.get_str('decksite_test_database')
    configuration.CONFIG['decksite_database'] = name
    db().execute(f'DROP DATABASE IF EXISTS {name}')
    db().execute(f'CREATE DATABASE {name}')
    db().execute(f'USE {name}')
    database.setup()
