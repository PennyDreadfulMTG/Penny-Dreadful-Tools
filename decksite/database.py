import os
from typing import Any

from flask import g, has_request_context, request

from shared import configuration, logger
from shared.container import Container
from shared.database import Database, get_database

TEST_CONTEXT = Container()

def db() -> Database:
    ctx: Any = TEST_CONTEXT  # Fallback context for testing.
    if has_request_context():  # type: ignore
        ctx = request
    elif g:
        ctx = g
    db_name = configuration.get_str('decksite_database')
    if not hasattr(ctx, db_name):
        setattr(ctx, db_name, get_database(db_name))
    return getattr(ctx, db_name)

def setup_in_app_context() -> None:
    from decksite import APP
    with APP.app_context():
        setup()

def setup() -> None:
    db().execute('CREATE TABLE IF NOT EXISTS db_version (version INTEGER UNIQUE NOT NULL)')
    version = db_version()
    patches = os.listdir('decksite/sql')
    patches.sort(key=lambda n: int(n.split('.')[0]))
    for fn in patches:
        path = os.path.join('decksite/sql', fn)
        n = int(fn.split('.')[0])
        if version < n:
            logger.warning(f'Patching database to v{n}')
            fh = open(path)
            sql = fh.read()
            for stmt in sql.split(';'):
                if stmt.strip() != '':
                    db().execute(stmt)
            fh.close()
            db().execute(f'INSERT INTO db_version (version) VALUES ({n})')

def db_version() -> int:
    return db().value('SELECT version FROM db_version ORDER BY version DESC LIMIT 1', [], 0)


setup_in_app_context()
