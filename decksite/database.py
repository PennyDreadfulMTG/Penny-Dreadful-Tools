import os

from shared import configuration
from shared.database import Database

def db():
    return DATABASE

def setup():
    db().execute('CREATE TABLE IF NOT EXISTS db_version (version INTEGER UNIQUE ON CONFLICT REPLACE NOT NULL)')
    version = db_version()
    for fn in os.listdir('decksite/sql'):
        path = os.path.join('decksite/sql', fn)
        n = int(fn.split('.')[0])
        if version < n:
            print("Patching database to v{0}".format(n))
            fh = open(path, 'r')
            sql = fh.read()
            for stmt in sql.split(';'):
                db().execute(stmt)
            fh.close()
            db().execute("INSERT INTO db_version (version) VALUES (?)", [n])

def db_version() -> int:
    return db().value('SELECT version FROM db_version ORDER BY version DESC LIMIT 1', [], 0)

DATABASE = Database(configuration.get('decksite_database'))
setup()
