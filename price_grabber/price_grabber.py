import datetime
import itertools
import sys

import ftfy

from magic import multiverse, oracle, seasons
from price_grabber import parser, price
from shared import configuration, dtutil, fetch_tools
from shared.database import get_database
from shared.pd_exception import DatabaseException, NotConfiguredException, TooFewItemsException

DATABASE = get_database(configuration.get_str('prices_database'))

def run() -> None:
    multiverse.init()
    oracle.init()
    fetch()
    price.cache()

def fetch() -> None:
    all_prices, timestamps = {}, []
    ch_urls = configuration.cardhoarder_urls.get()
    if not ch_urls:
        raise NotConfiguredException('No URLs found to get prices from')
    for _, url in enumerate(ch_urls):
        s = fetch_tools.fetch(url)
        s = ftfy.fix_encoding(s)
        timestamps.append(dtutil.parse_to_ts(s.split('\n', 1)[0].replace('UPDATED ', ''), '"%Y-%m-%dT%H:%M:%S+00:00"', dtutil.CARDHOARDER_TZ))
        all_prices[url] = parser.parse_cardhoarder_prices(s)
    if not timestamps:
        raise TooFewItemsException(f'Did not get any prices when fetching {list(itertools.chain(configuration.cardhoarder_urls.get()))} ({all_prices})')
    count = store(min(timestamps), all_prices)
    cleanup(count)

def store(timestamp: float, all_prices: dict[str, parser.PriceListType]) -> int:
    DATABASE.begin('store')
    lows: dict[str, int] = {}
    for code in all_prices:
        prices = all_prices[code]
        for name, p, _ in prices:
            cents = int(float(p) * 100)
            if cents < lows.get(name, sys.maxsize):
                lows[name] = cents
    count = 0
    while lows:
        count = count + 1
        sql = 'INSERT INTO low_price (`time`, name, price) VALUES '
        chunk = []
        try:
            for _ in range(0, 20):
                chunk.append(lows.popitem())
        except KeyError:
            pass  # Emptied it
        sql += ', '.join(['(%s, %s, %s)'] * len(chunk))
        values = []
        for name, cents in chunk:
            values.extend([timestamp, name, cents])
        execute(sql, values)
    DATABASE.commit('store')
    return count * 20

def cleanup(count: int = 0) -> None:
    beginning_of_season = seasons.last_rotation()
    one_month_ago = dtutil.now(dtutil.WOTC_TZ) - datetime.timedelta(31)
    oldest_needed = min(beginning_of_season, one_month_ago)
    limit = ''
    if count > 0:
        limit = f'LIMIT {count * 2}'
    execute('DELETE FROM low_price WHERE `time` < %s ' + limit, [dtutil.dt2ts(oldest_needed)])

def execute(sql: str, values: list[object] | None = None) -> None:
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
