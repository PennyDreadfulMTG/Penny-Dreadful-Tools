import csv
import json

import pkg_resources

from magic import configuration
from magic.fetcher_internal import FetchException, fetch, store, unzip


def legal_cards(force=False):
    resource_id = 'legal_cards'
    if force:
        resource_id = None
    return fetch('http://pdmtgo.com/legal_cards.txt', 'utf-8', resource_id).strip().split('\n')

def version():
    return pkg_resources.parse_version(json.loads(fetch('https://mtgjson.com/json/version.json')))

def mtgo_status():
    try:
        return json.loads(fetch('https://magic.wizards.com/sites/all/modules/custom/wiz_services/mtgo_status.php'))['status']
    except (FetchException, json.decoder.JSONDecodeError):
        return 'UNKNOWN'

def all_cards():
    s = unzip('https://mtgjson.com/json/AllCards-x.json.zip', 'AllCards-x.json')
    return json.loads(s)

def all_sets():
    s = unzip('https://mtgjson.com/json/AllSets.json.zip', 'AllSets.json')
    return json.loads(s)


def card_aliases():
    with open(configuration.get('card_alias_file'), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))

def whatsinstandard():
    return json.loads(fetch('http://whatsinstandard.com/api/4/sets.json'))

def fetch_prices():
    store('http://magic.bluebones.net/prices.db', configuration.get('pricesdb'))

def card_price(cardname):
    return json.loads(fetch('http://magic.bluebones.net:5800/{0}/'.format(cardname)))

def resources():
    return json.loads(fetch('http://magic.bluebones.net/pd/resources.json'))
