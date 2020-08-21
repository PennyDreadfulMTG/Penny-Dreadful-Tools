from decksite.database import db
from shared.pd_exception import DatabaseException
from shared import logger


def preaggregate(table: str, sql: str) -> None:
    lock_key = f'preaggregation:{table}'
    try:
        db().get_lock(lock_key, 60 * 5)
    except DatabaseException as e:
        logger.warning(f'Not preaggregating {table} because of {e}')
    db().execute(f'DROP TABLE IF EXISTS _new{table}')
    db().execute(sql)
    db().execute(f'DROP TABLE IF EXISTS _old{table}')
    db().execute(f'CREATE TABLE IF NOT EXISTS {table} (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute(f'RENAME TABLE {table} TO _old{table}, _new{table} TO {table}')
    db().execute(f'DROP TABLE IF EXISTS _old{table}')
    db().release_lock(lock_key)
