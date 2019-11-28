from shared import configuration
from shared.container import Container
from shared.database import Database, get_database

DATABASE = Container()

def db() -> Database:
    if not DATABASE.get('logsite_database'):
        DATABASE.logsite_database = get_database(configuration.get_str('logsite_database'))
    return DATABASE.logsite_database
