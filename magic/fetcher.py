import csv
import json
import os
from collections import OrderedDict
from urllib import parse
from functools import wraps
import time as py_time

import pkg_resources
from github import Github

import magic.fetcher_internal as internal
from magic.fetcher_internal import FetchException
from shared import configuration, dtutil
from shared.pd_exception import TooFewItemsException

def stagger(delay=0.1):
    def decorator(func_in):
        @wraps(func_in)
        def func_out(*args, **kwargs):
            if py_time.time() - func_out.last_call < delay:
                func_out.last_call = py_time.time() + delay
                py_time.sleep(delay - (py_time.time() - func_out.last_call))
            return func_in(*args, **kwargs)
        func_out.last_call = float("-inf")
        return func_out
    return decorator


def all_cards():
    try:
        return json.load(open('AllCards-x.json'))
    except FileNotFoundError:
        s = internal.unzip('https://mtgjson.com/json/AllCards-x.json.zip', 'AllCards-x.json')
        return json.loads(s)

def all_sets():
    try:
        return json.load(open('AllSets.json'))
    except FileNotFoundError:
        s = internal.unzip('https://mtgjson.com/json/AllSets.json.zip', 'AllSets.json')
        return json.loads(s)

def bugged_cards():
    text = internal.fetch('https://pennydreadfulmtg.github.io/modo-bugs/bugs.tsv')
    if text is None:
        return None
    lines = [l.split('\t') for l in text.split('\n')]
    return lines[1:-1]

def card_aliases():
    with open(configuration.get('card_alias_file'), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))


def card_price(cardname):
    return internal.fetch_json('http://katelyngigante.com:5800/{0}/'.format(cardname.replace('//', '-split-')))

def card_price_string(card, short=False):
    def price_info(c):
        try:
            p = card_price(c.name)
        except FetchException:
            return "Price unavailable"
        if p is None:
            return "Not available online"
        # Currently disabled
        s = '{price}'.format(price=format_price(p['price']))
        if float(p['low']) <= 0.05:
            s += ' (low {low}, high {high}'.format(low=format_price(p['low']), high=format_price(p['high']))
            if float(p['low']) <= 0.01 and not short:
                s += ', {week}% this week, {month}% this month, {season}% this season'.format(week=round(float(p['week']) * 100.0), month=round(float(p['month']) * 100.0), season=round(float(p['season']) * 100.0))
            s += ')'
        age = dtutil.dt2ts(dtutil.now()) - p['time']
        if age > 60 * 60 * 2:
            s += '\nWARNING: price information is {display} old'.format(display=dtutil.display_time(age, 1))
        return s
    def format_price(p):
        if p is None:
            return 'Unknown'
        dollars, cents = str(round(float(p), 2)).split('.')
        return '{dollars}.{cents}'.format(dollars=dollars, cents=cents.ljust(2, '0'))
    return price_info(card)

def cardhoarder_url(d):
    cs = {}
    for entry in d.maindeck + d.sideboard:
        name = entry['card'].name
        cs[name] = cs.get(name, 0) + entry['n']
    deck_s = '||'.join([str(v) + ' ' + k.replace(' // ', '/').replace('"', '') for k, v in cs.items()])
    return 'https://www.cardhoarder.com/decks/upload?deck={deck}'.format(deck=internal.escape(deck_s))

def create_github_issue(title, author, repo='PennyDreadfulMTG/Penny-Dreadful-Tools'):
    if configuration.get('github_user') is None or configuration.get('github_password') is None:
        return None
    if title is None or title == '':
        return None
    g = Github(configuration.get('github_user'), configuration.get('github_password'))
    repo = g.get_repo(repo)
    body = ''
    if '\n' in title:
        title, body = title.split('\n', 1)
        body += '\n\n'
    body += 'Reported on Discord by {author}'.format(author=author)
    issue = repo.create_issue(title=title, body=body)
    return issue

def decksite_url(path='/'):
    hostname = configuration.get('decksite_hostname')
    port = configuration.get('decksite_port')
    if port != 80:
        hostname = '{hostname}:{port}'.format(hostname=hostname, port=port)
    return parse.urlunparse((configuration.get('decksite_protocol'), hostname, path, None, None, None))

def legal_cards(force=False, season=None):
    if season is None and os.path.exists('legal_cards.txt'):
        print("HACK: Using local legal_cards override.")
        h = open('legal_cards.txt')
        legal = h.readlines()
        h.close()
        return [l.strip() for l in legal]
    if season is None:
        url = 'http://pdmtgo.com/legal_cards.txt'
    else:
        url = 'http://pdmtgo.com/{season}_legal_cards.txt'.format(season=season)
    encoding = 'utf-8' if season != 'EMN' else 'latin-1' # EMN was encoded weirdly.
    legal_txt = internal.fetch(url, encoding, force=force)
    return legal_txt.strip().split('\n')

def mtgjson_version():
    return pkg_resources.parse_version(internal.fetch_json('https://mtgjson.com/json/version.json'))

def mtgo_status():
    try:
        return internal.fetch_json('https://magic.wizards.com/sites/all/modules/custom/wiz_services/mtgo_status.php')['status']
    except (FetchException, json.decoder.JSONDecodeError):
        return 'UNKNOWN'

def resources():
    with open('decksite/resources.json') as resources_file:
        return json.load(resources_file, object_pairs_hook=OrderedDict)

def scryfall_cards():
    url = 'https://api.scryfall.com/cards'
    return internal.fetch_json(url)

@stagger(0.1)
def search_scryfall(query):
    """Returns a tuple. First member is bool indicating whether there were too many cards to search,
    second member is a list of card names."""
    max_n_queries = 2 #API returns 60 cards at once. Indicate how many pages max should be shown.
    if query == '':
        return False, []
    result_json = internal.fetch_json('https://api.scryfall.com/cards/search?q=' + internal.escape(query), character_encoding='utf-8')
    if 'code' in result_json.keys(): #the API returned an error
        if result_json['status'] == 404: #no cards found
            print('Scryfall search yielded 0 results.')
            return False, []
        print('Error fetching scryfall data:\n', result_json)
        return False, []
    for warning in result_json.get('warnings', []): #scryfall-provided human-readable warnings
        print(warning) # Why aren't we displaying these to the user?
    too_many_cards = result_json['total_cards'] > max_n_queries * 60
    result_data = result_json['data']
    for _ in range(max_n_queries - 1): #fetch the remaining pages
        if not result_json['has_more']:
            break
        result_json = internal.fetch_json(result_json['next_page'])
        result_data.extend(result_json.get('data', []))

    result_data.sort(key=lambda x: x['legalities']['penny'])

    def get_frontside(scr_card):
        """If card is transform, returns first name. Otherwise, returns name.
        This is to make sure cards are later found in the database"""
        #not sure how to handle meld cards
        if scr_card['layout'] in ['transform', 'flip']:
            return scr_card['card_faces'][0]['name']
        return scr_card['name']
    result_cardnames = [get_frontside(obj) for obj in result_data]
    return too_many_cards, result_cardnames

def sitemap():
    return internal.fetch_json(decksite_url('/api/sitemap/'))

def time(q):
    no_results_msg = 'ZERO_RESULTS'
    url = 'http://maps.googleapis.com/maps/api/geocode/json?address={q}&sensor=false'.format(q=internal.escape(q))
    info = internal.fetch_json(url)
    try:
        location = info['results'][0]['geometry']['location']
    except IndexError as e:
        raise TooFewItemsException(e)
    url = 'https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&sensor=false'.format(lat=internal.escape(str(location['lat'])), lng=internal.escape(str(location['lng'])), timestamp=internal.escape(str(dtutil.dt2ts(dtutil.now()))))
    timezone_info = internal.fetch_json(url)
    if timezone_info['status'] == no_results_msg:
        raise TooFewItemsException(no_results_msg)
    return dtutil.now(dtutil.timezone(timezone_info['timeZoneId'])).strftime('%l:%M %p')

def whatsinstandard():
    return internal.fetch_json('http://whatsinstandard.com/api/v5/sets.json')
