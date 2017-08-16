import csv
import json
import os
from collections import OrderedDict
from urllib import parse

import pkg_resources
from github import Github

import magic.fetcher_internal as internal
from magic.fetcher_internal import FetchException
from shared import configuration, dtutil

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

def card_aliases():
    with open(configuration.get('card_alias_file'), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))

def whatsinstandard():
    return internal.fetch_json('http://whatsinstandard.com/api/v5/sets.json')

def card_price(cardname):
    return internal.fetch_json('http://katelyngigante.com:5800/{0}/'.format(cardname.replace('//', '-split-')))

def resources():
    with open('decksite/resources.json') as resources_file:
        return json.load(resources_file, object_pairs_hook=OrderedDict)

def create_github_issue(title, author):
    if configuration.get("github_user") is None or configuration.get("github_password") is None:
        return None
    if title is None or title == "":
        return None
    g = Github(configuration.get("github_user"), configuration.get("github_password"))
    repo = g.get_repo("PennyDreadfulMTG/Penny-Dreadful-Tools")
    issue = repo.create_issue(title=title, body="Reported on Discord by {author}".format(author=author))
    return issue

def bugged_cards():
    text = internal.fetch('https://pennydreadfulmtg.github.io/modo-bugs/bugs.tsv')
    if text is None:
        return None
    lines = [l.split('\t') for l in text.split('\n')]
    return lines[1:-1]

def sitemap():
    return internal.fetch_json(decksite_url('/api/sitemap/'))

def time(q):
    url = 'http://maps.googleapis.com/maps/api/geocode/json?address={q}&sensor=false'.format(q=internal.escape(q))
    info = internal.fetch_json(url)
    try:
        location = info['results'][0]['geometry']['location']
    except IndexError:
        return 'Location unknown.'
    url = 'https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&sensor=false'.format(lat=internal.escape(str(location['lat'])), lng=internal.escape(str(location['lng'])), timestamp=internal.escape(str(dtutil.dt2ts(dtutil.now()))))
    timezone_info = internal.fetch_json(url)
    return dtutil.now(dtutil.timezone(timezone_info['timeZoneId'])).strftime('%l:%M %p')

def decksite_url(path='/'):
    hostname = configuration.get('decksite_hostname')
    port = configuration.get('decksite_port')
    if port != 80:
        hostname = '{hostname}:{port}'.format(hostname=hostname, port=port)
    return parse.urlunparse((configuration.get('decksite_protocol'), hostname, path, None, None, None))

def cardhoarder_url(d):
    deck_s = '||'.join([str(entry['n']) + ' ' + entry['card'].name.replace(' // ', '/').replace('"', '') for entry in d.maindeck + d.sideboard])
    return 'https://www.cardhoarder.com/decks/upload?deck={deck}'.format(deck=internal.escape(deck_s))