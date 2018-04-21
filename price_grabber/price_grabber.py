import sys
from typing import Dict, List, Optional

import ftfy

from magic import fetcher_internal, multiverse, oracle
from price_grabber import parser, price
from shared import configuration, dtutil
from shared.database import get_database
from shared.pd_exception import DatabaseException, TooFewItemsException

DATABASE = get_database(configuration.get_str('prices_database'))

def run() -> None:
    multiverse.init()
    oracle.init()
    fetch()
    price.cache()

def fetch() -> None:
    all_prices, timestamps = {}, []
    for _, url in enumerate(configuration.get_list('cardhoarder_urls')):
        s = fetcher_internal.fetch(url)
        s = ftfy.fix_encoding(s)
        timestamps.append(dtutil.parse_to_ts(s.split('\n', 1)[0].replace('UPDATED ', ''), '%Y-%m-%dT%H:%M:%S+00:00', dtutil.CARDHOARDER_TZ))
        all_prices[url] = parser.parse_cardhoarder_prices(s)
    url = configuration.get_str('mtgotraders_url')
    if url:
        s = fetcher_internal.fetch(url)
        timestamps.append(dtutil.dt2ts(dtutil.now()))
        all_prices['mtgotraders'] = parser.parse_mtgotraders_prices(s)
    if not timestamps:
        raise TooFewItemsException('Did not get any prices when fetching {urls} ({all_prices})'.format(urls=configuration.get_list('cardhoarder_urls') + [configuration.get_str('mtgotraders_url')], all_prices=all_prices))
    store(min(timestamps), all_prices)


def store(timestamp: float, all_prices: Dict[str, parser.PriceList]) -> None:
    DATABASE.begin()
    lows: Dict[str, int] = {}
    for code in all_prices:
        prices = all_prices[code]
        for name, p, _ in prices:
            cents = int(float(p) * 100)
            if cents < lows.get(name, sys.maxsize):
                lows[name] = cents
    while lows:
        sql = 'INSERT INTO low_price (`time`, name, price) VALUES '
        chunk = []
        try:
            for _ in range(0, 20): # type: ignore
                chunk.append(lows.popitem())
        except KeyError:
            pass # Emptied it
        sql += ', '.join(['(%s, %s, %s)'] * len(chunk))
        values = []
        for name, cents in chunk:
            values.extend([timestamp, name, cents])
        execute(sql, values)
        DATABASE.commit()

def execute(sql: str, values: Optional[List[object]] = None) -> None:
    if values is None:
        values = []
    try:
        DATABASE.execute(sql, values)
    except DatabaseException as e:
        print(e)
        # If you wish to make an apple pie from scratch, you must first invent the universe.
        create_tables()
        execute(sql, values)

def create_tables() -> None:
    print('Creating price tables.')
    sql = """CREATE TABLE IF NOT EXISTS cache (
        `time` INTEGER,
        name VARCHAR(150),
        high MEDIUMINT UNSIGNED,
        low MEDIUMINT UNSIGNED,
        price MEDIUMINT UNSIGNED,
        week FLOAT,
        month FLOAT,
        season FLOAT,
        INDEX idx_name_price (price)
    )"""
    execute(sql)
    sql = """CREATE TABLE IF NOT EXISTS low_price (
        `time` INTEGER,
        name VARCHAR(150),
        price MEDIUMINT UNSIGNED,
        INDEX idx_name_time_price (name, `time`, price)
    )"""
    execute(sql)
