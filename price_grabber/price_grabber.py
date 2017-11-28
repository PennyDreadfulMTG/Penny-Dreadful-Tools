import html
import re
import sys
import time
import urllib

from magic import card, fetcher_internal, multiverse, oracle
from magic.database import db
from shared import configuration
from shared.database import get_database
from shared.pd_exception import DatabaseException

from price_grabber import price

DATABASE = get_database(configuration.get('prices_database'))
CARDS = {}

def run():
    oracle.init()
    fetch()
    price.cache()

def fetch():
    all_prices = {}
    url = 'https://www.mtggoldfish.com/prices/select'
    s = fetcher_internal.fetch(url)
    sets = parse_sets(s) + ['TD0', 'TD2'] # Theme decks pages not linked from /prices/select
    for s in ['PD2', 'PD3']: # Fake sets that appear in the index
        sets.remove(s)

    for code in sets:
        for suffix in ['', '_F']:
            if code == 'PZ2' and suffix == '_F':
                print('Explicitly skipping PZ2_F because it is a lie.')
                continue
            code = '{code}{suffix}'.format(code=code, suffix=suffix)
            url = set_url(code)
            time.sleep(1)
            s = fetcher_internal.fetch(url, force=True)
            prices = parse_prices(s)
            if not prices:
                print('Found no prices for {code}'.format(code=code))
            all_prices[code] = prices
    timestamp = int(time.time())
    store(timestamp, all_prices)

def set_url(code):
    return 'https://www.mtggoldfish.com/index/{code}#online'.format(code=urllib.parse.quote(code))

def parse_sets(s):
    # Exclude codes with underscores, dashes and lowercase because they are pages for standard, modern, etc. and will gives us dupes.
    return re.findall("'/index/([A-Z0-9]+)'", s)

def parse_prices(s):
    results = re.findall(r"""<td class='card'><a.*?href="[^#]*#online".*?>([^\(<]*)(?:\([^\)]*\))?</a></td>\n<td>[^<]*</td>\n<td>[^<]*</td>\n<td class='text-right'>\n(.*)\n</td>""", s)
    return [(name_lookup(html.unescape(name.strip())), html.unescape(price.strip())) for name, price in results if name_lookup(html.unescape(name.strip())) is not None]

def store(timestamp, all_prices):
    DATABASE.begin()
    lows = {}
    for code in all_prices:
        prices = all_prices[code]
        for name, p in prices:
            cents = int(float(p) * 100)
            if cents < lows.get(name, sys.maxsize):
                lows[name] = cents
    sql = 'INSERT INTO low_price (`time`, name, price) VALUES '
    sql += ", ".join(['(?, ?, ?)'] * len(lows))
    values = []
    for name, cents in lows.items():
        values.extend([timestamp, name, cents])
    execute(sql, values)
    DATABASE.commit()

def execute(sql, values=None):
    if values is None:
        values = []
    try:
        DATABASE.execute(sql, values)
    except DatabaseException as e:
        print(e)
        # If you wish to make an apple pie from scratch, you must first invent the universe.
        create_tables()
        execute(sql, values)

def create_tables():
    print('Creating price tables.')
    sql = """CREATE TABLE IF NOT EXISTS cache (
        `time` INTEGER,
        name VARCHAR(150),
        high MEDIUMINT UNSIGNED,
        low MEDIUMINT UNSIGNED,
        price MEDIUMINT UNSIGNED,
        week FLOAT,
        month FLOAT,
        season FLOAT
    )"""
    execute(sql)
    sql = """CREATE TABLE IF NOT EXISTS low_price (
        `time` INTEGER,
        name VARCHAR(150),
        price MEDIUMINT UNSIGNED,
        INDEX idx_name_time_price (name, `time`, price)
    )"""
    execute(sql)

def name_lookup(name):
    if not CARDS:
        rs = db().execute(multiverse.base_query())
        for row in rs:
            CARDS[card.canonicalize(row['name'])] = row['name']
    canonical = card.canonicalize(name)
    if canonical not in CARDS:
        print("Bogus name {name} ({canonical}) found.".format(name=name, canonical=canonical))
        return None
    return CARDS[canonical]
