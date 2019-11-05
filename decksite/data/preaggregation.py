from decksite.database import db

def preaggregate(table, sql) -> None:
    db().execute(f'DROP TABLE IF EXISTS _new{table}')
    db().execute(sql)
    db().execute(f'DROP TABLE IF EXISTS _old{table}')
    db().execute(f'CREATE TABLE IF NOT EXISTS {table} (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute(f'RENAME TABLE {table} TO _old{table}, _new{table} TO {table}')
    db().execute(f'DROP TABLE IF EXISTS _old{table}')
