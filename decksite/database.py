import os

from flask import g, has_request_context, request

from shared import configuration
from shared.container import Container
from shared.database import Database, get_database
from shared_web import logger


def db() -> Database:
    if has_request_context():  # type: ignore
        ctx = request
    elif g:
        ctx = g
    else:
        ctx = Container() # Fallback context for testing.
    if not hasattr(ctx, 'database'):
        ctx.database = get_database(configuration.get_str('decksite_database'))
    return ctx.database

def setup() -> None:
    # pylint: disable=import-outside-toplevel
    from decksite import APP
    with APP.app_context():  # type: ignore
        db().execute('CREATE TABLE IF NOT EXISTS db_version (version INTEGER UNIQUE NOT NULL)')
        version = db_version()
        sqldir = os.path.join(os.path.dirname(__file__), 'sql')
        patches = os.listdir(sqldir)
        patches.sort(key=lambda n: int(n.split('.')[0]))
        for fn in patches:
            path = os.path.join(sqldir, fn)
            n = int(fn.split('.')[0])
            if version < n:
                logger.warning('Patching database to v{0}'.format(n))
                fh = open(path, 'r')
                sql = fh.read()
                for stmt in sql.split(';'):
                    if stmt.strip() != '':
                        db().execute(stmt)
                fh.close()
                db().execute('INSERT INTO db_version (version) VALUES ({n})'.format(n=n))

def db_version() -> int:
    return db().value('SELECT version FROM db_version ORDER BY version DESC LIMIT 1', [], 0)

setup()
