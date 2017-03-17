import os
import time

import apsw

from magic import fetcher, rotation
from shared import configuration, database


def info(card, force=False):
    if not force:
        r = info_cached(card)
        if r is not None:
            return r
    cache()
    return info_cached(card)

def info_cached(card=None, name=None):
    if name is None and card is not None:
        name = card.name
    sql = 'SELECT `time`, low / 100.0 AS low, high / 100.0 aS high, price / 100.0 AS price, week, month, season FROM cache WHERE name = ?'
    conn = apsw.Connection(configuration.get('pricesdb'))
    conn.setrowtrace(database.database_sqlite.row_factory)
    return conn.cursor().execute(sql, [name]).fetchone()

def cache():
    conn = apsw.Connection(configuration.get('pricesdb'))

    now = time.time()
    week = now - 60 * 60 * 24 * 7
    month = now - 60 * 60 * 24 * 7 * 30
    last_rotation = rotation.last_rotation().timestamp()

    sql = 'SELECT MAX(`time`) FROM price'
    latest = conn.cursor().execute(sql).fetchone()[0]
    conn.cursor().execute('BEGIN TRANSACTION')
    conn.cursor().execute('DELETE FROM cache')
    sql = """
        INSERT INTO cache (`time`, name, price, low, high, week, month, season)
            SELECT
                MAX(`time`) AS `time`,
                name,
                MIN(CASE WHEN `time` = ? THEN price ELSE 999999 END) AS price,
                MIN(price) AS low,
                MAX(price) AS high,
                CAST(SUM(CASE WHEN `time` > ? AND price = 1 THEN 1 ELSE 0 END) AS REAL) / CAST(SUM(CASE WHEN `time` > ? THEN 1 ELSE 0 END) AS REAL) AS week,
                CAST(SUM(CASE WHEN `time` > ? AND price = 1 THEN 1 ELSE 0 END) AS REAL) / CAST(SUM(CASE WHEN `time` > ? THEN 1 ELSE 0 END) AS REAL) AS month,
                CAST(SUM(CASE WHEN `time` > ? AND price = 1 THEN 1 ELSE 0 END) AS REAL) / CAST(SUM(CASE WHEN `time` > ? THEN 1 ELSE 0 END) AS REAL) AS season
            FROM
                (SELECT
                    `time`,
                    name,
                    MIN(price) AS price
                FROM price
                WHERE `time` > ?
                GROUP BY `time`, name)
            GROUP BY name;
    """
    conn.cursor().execute(sql, [latest, week, week, month, month, last_rotation, last_rotation, last_rotation])
    conn.cursor().execute('COMMIT')

def download_full_db():
    if not os.path.isfile(configuration.get('pricesdb')) or os.path.getmtime(configuration.get('pricesdb')) < time.time() - 60 * 60 * 24:
        fetcher.fetch_prices()
