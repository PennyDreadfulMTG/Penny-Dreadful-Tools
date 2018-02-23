import os

from flask import g, has_request_context, request

from decksite import APP
from shared import configuration
from shared.database import get_database


def db():
    if has_request_context():
        ctx = request
    else:
        ctx = g
    if not hasattr(ctx, 'database'):
        ctx.database = get_database(configuration.get('decksite_database'))
    return ctx.database

def setup():
    db().execute('CREATE TABLE IF NOT EXISTS db_version (version INTEGER UNIQUE NOT NULL)')
    version = db_version()
    patches = os.listdir('decksite/sql')
    patches.sort(key=lambda n: int(n.split('.')[0]))
    for fn in patches:
        path = os.path.join('decksite/sql', fn)
        n = int(fn.split('.')[0])
        if version < n:
            print("Patching database to v{0}".format(n))
            fh = open(path, 'r')
            sql = fh.read()
            for stmt in sql.split(';'):
                if stmt.strip() != "":
                    db().execute(stmt)
            fh.close()
            db().execute("INSERT INTO db_version (version) VALUES ({n})".format(n=n))

def db_version() -> int:
    return db().value('SELECT version FROM db_version ORDER BY version DESC LIMIT 1', [], 0)

with APP.app_context():
    setup()
