from decksite.database import db
from magic import seasons
from shared import logger
from shared.pd_exception import DatabaseException


def preaggregate(table: str, sql: str) -> None:
    lock_key = f'preaggregation:{table}'
    try:
        db().get_lock(lock_key, 60 * 5)
    except DatabaseException as e:
        logger.warning(f'Not preaggregating {table} because of {e}')
    db().execute(f'DROP TABLE IF EXISTS _new{table}')
    db().execute(sql)
    db().execute(f'DROP TABLE IF EXISTS _old{table}')
    db().execute(f'CREATE TABLE IF NOT EXISTS {table} (_ INT)')  # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute(f'RENAME TABLE {table} TO _old{table}, _new{table} TO {table}')
    db().execute(f'DROP TABLE IF EXISTS _old{table}')
    db().release_lock(lock_key)

# Preaggregate season-by-season instead of in one horking great SQL query.
def preaggregate2(table: str, table_creation_sql: str, preaggregation_sql: str) -> None:
    logger.info(f'Preaggregating {table}')
    lock_key = f'preaggregation:{table}'
    try:
        db().get_lock(lock_key, 60 * 60)
    except DatabaseException as e:
        logger.warning(f'Not preaggregating {table} because of {e}')
    db().execute(f'DROP TABLE IF EXISTS _new{table}')
    db().execute(table_creation_sql)
    for season_id in range(1, len(seasons.SEASONS) - 1):
        db().execute(preaggregation_sql.format(season_id=season_id))
    db().execute(f'DROP TABLE IF EXISTS _old{table}')
    db().execute(f'CREATE TABLE IF NOT EXISTS {table} (_ INT)')  # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute(f'RENAME TABLE {table} TO _old{table}, _new{table} TO {table}')
    db().execute(f'DROP TABLE IF EXISTS _old{table}')
    db().release_lock(lock_key)
    logger.info(f'Finished preaggregating {table}')
