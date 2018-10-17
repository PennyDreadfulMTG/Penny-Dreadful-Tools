import time
from typing import Optional

from mypy_extensions import TypedDict

from magic import rotation
from magic.models.card import Card
from shared import configuration, database

PriceDataType = TypedDict('PriceDataType', {
    'time': int,
    'low': str,
    'high': str,
    'price': str,
    'week': float,
    'month': float,
    'season': float,
    })

def info(card: Card, force: bool = False) -> Optional[PriceDataType]:
    if not force:
        r = info_cached(card)
        if r is not None:
            return r
    cache()
    return info_cached(card)

def info_cached(card: Card = None, name: str = None) -> Optional[PriceDataType]:
    if name is None and card is not None:
        name = card.name
    sql = 'SELECT `time`, low / 100.0 AS low, high / 100.0 AS high, price / 100.0 AS price, week, month, season FROM cache WHERE name = %s'
    db = database.get_database(configuration.get_str('prices_database'))
    try:
        return db.select(sql, [name])[0] # type: ignore
    except IndexError:
        return None

def cache() -> None:
    db = database.get_database(configuration.get_str('prices_database'))

    now = round(time.time())
    week = now - 60 * 60 * 24 * 7
    month = now - 60 * 60 * 24 * 7 * 30
    last_rotation = int(rotation.last_rotation().timestamp())

    sql = 'SELECT MAX(`time`) FROM low_price'
    latest = db.value(sql)

    db.begin('cache')
    db.execute('DELETE FROM cache')
    sql = """
        INSERT INTO cache (`time`, name, price, low, high, week, month, season)
            SELECT
                MAX(`time`) AS `time`,
                name,
                MIN(CASE WHEN `time` = %s THEN price END) AS price,
                MIN(CASE WHEN `time` > %s THEN price END) AS low,
                MAX(CASE WHEN `time` > %s THEN price END) AS high,
                AVG(CASE WHEN `time` > %s AND price = 1 THEN 1 WHEN `time` > %s THEN 0 END) AS week,
                AVG(CASE WHEN `time` > %s AND price = 1 THEN 1 WHEN `time` > %s THEN 0 END) AS month,
                AVG(CASE WHEN `time` > %s AND price = 1 THEN 1 WHEN `time` > %s THEN 0 END) AS season
            FROM low_price
            GROUP BY name;
    """
    db.execute(sql, [latest, last_rotation, last_rotation, week, week, month, month, last_rotation, last_rotation])
    db.commit('cache')
