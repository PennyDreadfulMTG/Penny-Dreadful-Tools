import time

from magic import rotation
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
    sql = 'SELECT `time`, low / 100.0 AS low, high / 100.0 AS high, price / 100.0 AS price, week, month, season FROM cache WHERE name = %s'
    db = database.get_database(configuration.get('prices_database'))
    return db.execute(sql, [name])[0]

def cache():
    db = database.get_database(configuration.get('prices_database'))

    now = int(time.time())
    week = now - 60 * 60 * 24 * 7
    month = now - 60 * 60 * 24 * 7 * 30
    last_rotation = int(rotation.last_rotation().timestamp())

    sql = 'SELECT MAX(`time`) FROM low_price'
    latest = db.value(sql)

    db.begin()
    db.execute('DELETE FROM cache')
    sql = """
        INSERT INTO cache (`time`, name, price, low, high, week, month, season)
            SELECT
                MAX(`time`) AS `time`,
                name,
                MIN(CASE WHEN `time` = ? THEN price ELSE 999999 END) AS price,
                MIN(price) AS low,
                MAX(price) AS high,
                SUM(CASE WHEN `time` > ? AND price = 1 THEN 1 ELSE 0 END) / SUM(CASE WHEN `time` > ? THEN 1 ELSE 0 END) AS week,
                SUM(CASE WHEN `time` > ? AND price = 1 THEN 1 ELSE 0 END) / SUM(CASE WHEN `time` > ? THEN 1 ELSE 0 END) AS month,
                SUM(CASE WHEN `time` > ? AND price = 1 THEN 1 ELSE 0 END) / SUM(CASE WHEN `time` > ? THEN 1 ELSE 0 END) AS season
            FROM low_price
            GROUP BY name;
    """
    db.execute(sql, [latest, week, week, month, month, last_rotation, last_rotation])
    db.commit()
