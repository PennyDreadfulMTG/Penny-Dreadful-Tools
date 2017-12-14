import html
import re
import sys

from magic import card, fetcher_internal, multiverse, oracle
from magic.database import db
from shared import configuration, dtutil
from shared.database import get_database
from shared.pd_exception import DatabaseException

from price_grabber import price

DATABASE = get_database(configuration.get('prices_database'))
CARDS = {}

def run():
    multiverse.init()
    oracle.init()
    fetch()
    price.cache()

def fetch():
    all_prices, timestamps = {}, []
    for i, url in enumerate(configuration.get('cardhoarder_urls')):
        s = fetcher_internal.fetch(url)
        timestamps.append(dtutil.parse_to_ts(s.split('\n', 1)[0].replace('UPDATED ', ''), '%Y-%m-%dT%H:%M:%S+00:00', dtutil.CARDHOARDER_TZ))
        all_prices[i] = parse_prices(s)
    store(min(timestamps), all_prices)

def parse_prices(s):
    details = []
    for line in s.splitlines()[2:]: # Skipping date and header line.
        if line.count('\t') != 6:
            print('Bad line: {line}'.format(line=line))
        else:
            _mtgo_id, mtgo_set, _mtgjson_set, set_number, name, p, quantity = line.split('\t')  # pylint: disable=unused-variable
            if int(quantity) > 0 and not mtgo_set.startswith('CH-') and mtgo_set != 'VAN' and mtgo_set != 'EVENT' and not re.search(r'(Booster|Commander Deck|Commander:|Theme Deck|Draft Pack|Duel Decks|Reward Pack|Intro Pack|Tournament Pack|Premium Deck Series:|From the Vault)', name):
                details.append((name, p))
    return [(name_lookup(html.unescape(name.strip())), html.unescape(p.strip())) for name, p in details if name_lookup(html.unescape(name.strip())) is not None]

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
    if name == 'Kongming, Sleeping Dragon':
        name = 'Kongming, "Sleeping Dragon"'
    elif name == 'Pang Tong, Young Phoenix':
        name = 'Pang Tong, "Young Phoenix"'
    if not CARDS:
        rs = db().execute(multiverse.base_query())
        for row in rs:
            CARDS[card.canonicalize(row['name'])] = row['name']
    canonical = card.canonicalize(name)
    if canonical not in CARDS:
        print("Bogus name {name} ({canonical}) found.".format(name=name, canonical=canonical))
        return None
    return CARDS[canonical]
