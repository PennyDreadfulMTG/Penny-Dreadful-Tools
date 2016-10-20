import html
import re
import sqlite3
import time
import urllib

import fetcher
import price

DATABASE = sqlite3.connect('prices.db')

def fetch():
    all_prices = {}
    url = 'https://www.mtggoldfish.com/prices/select'
    s = fetcher.fetch(url)
    sets = parse_sets(s)
    for code in sets:
        for suffix in ['', '_F']:
            code = '{code}{suffix}'.format(code=code, suffix=suffix)
            url = set_url(code)
            s = fetcher.fetch(url)
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
    results = re.findall("""<td class='card'><a data-full-image="[^"]*" data-html="true" data-trigger="hover" href="[^#]*#online" rel="popover">([^<]*)</a></td>\n<td>[^<]*</td>\n<td>[^<]*</td>\n<td class='text-right'>\n(.*)\n</td>""", s)
    return [(html.unescape(name), html.unescape(price)) for name, price in results]

def store(timestamp, all_prices):
    sql = 'INSERT INTO price (`time`, name, `set`, premium, price) VALUES (?, ?, ?, ?, ?)'
    for code in all_prices:
        prices = all_prices[code]
        try:
            code, premium = code.split('_')
            premium = True
        except ValueError:
            premium = False
        for name, p in prices:
            cents = int(float(p) * 100)
            execute(sql, [timestamp, name, code, premium, cents])
    commit()

def execute(sql, values=None):
    if values is None:
        values = []
    try:
        DATABASE.cursor().execute(sql, values)
    except sqlite3.OperationalError as e:
        print(e)
        # If you wish to make an apple pie from scratch, you must first invent the universe.
        create_tables()
        execute(sql, values)

def commit():
    DATABASE.commit()
    DATABASE.close()

def create_tables():
    print('Creating price tables.')
    sql = """CREATE TABLE IF NOT EXISTS price (
        `time` INTEGER,
        name TEXT,
        `set` TEXT,
        premium INTEGER,
        price INTEGER
    )"""
    execute(sql)
    sql = """CREATE TABLE IF NOT EXISTS cache (
        `time` INTEGER,
        name TEXT,
        high INTEGER,
        low INTEGER,
        price INTEGER,
        week REAL,
        month REAL,
        season REAL
    )"""
    execute(sql)

fetch()
price.cache()
