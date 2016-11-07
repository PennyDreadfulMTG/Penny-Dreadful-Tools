import csv
import json
from collections import OrderedDict

import pkg_resources
from github import Github

import magic.fetcher_internal as internal
from magic.fetcher_internal import FetchException
from shared import configuration


def legal_cards(force=False, season=None):
    url = 'http://pdmtgo.com/legal_cards.txt'
    resource_id = 'legal_cards'
    if season is not None:
        resource_id = "{season}_legal_cards".format(season=season)
        url = 'http://pdmtgo.com/{season}_legal_cards.txt'.format(season=season)
        if season == "EMN":
            # EMN was encoded weirdly.
            return internal.fetch(url, 'latin-1', resource_id).strip().split('\n')
    if force:
        resource_id = None
    return internal.fetch(url, 'utf-8', resource_id).strip().split('\n')

def mtgjson_version():
    return pkg_resources.parse_version(internal.fetch_json('https://mtgjson.com/json/version.json', resource_id='mtg_json_version'))

def mtgo_status():
    try:
        return internal.fetch_json('https://magic.wizards.com/sites/all/modules/custom/wiz_services/mtgo_status.php')['status']
    except (FetchException, json.decoder.JSONDecodeError):
        return 'UNKNOWN'

def all_cards():
    s = internal.unzip('https://mtgjson.com/json/AllCards-x.json.zip', 'AllCards-x.json')
    return json.loads(s)

def all_sets():
    s = internal.unzip('https://mtgjson.com/json/AllSets.json.zip', 'AllSets.json')
    return json.loads(s)

def card_aliases():
    with open(configuration.get('card_alias_file'), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))

def whatsinstandard():
    return internal.fetch_json('http://whatsinstandard.com/api/4/sets.json', resource_id='whatsinstandard')

def fetch_prices():
    internal.store('http://magic.bluebones.net/prices.db', configuration.get('pricesdb'))

def card_price(cardname):
    return internal.fetch_json('http://magic.bluebones.net:5800/{0}/'.format(cardname))

def resources():
    with open('decksite/resources.json') as resources_file:
        return json.load(resources_file, object_pairs_hook=OrderedDict)

def post(url, data):
    return internal.post(url, data)

def create_github_issue(title, author):
    g = Github(configuration.get("github_user"), configuration.get("github_password"))
    repo = g.get_repo("PennyDreadfulMTG/Penny-Dreadful-Tools")
    issue = repo.create_issue(title=title, body="Reported on Discord by {author}".format(author=author))
    return issue
