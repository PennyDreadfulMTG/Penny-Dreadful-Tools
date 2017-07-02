import csv
import json
import os
import re
from collections import OrderedDict
from datetime import datetime

import pkg_resources
from github import Github
from pytz import timezone

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
    legal_txt = internal.fetch(url, 'utf-8', resource_id, can_304=True)
    if legal_txt is None:
        return None
    return legal_txt.strip().split('\n')

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
    text = internal.fetch("https://pennydreadfulmtg.github.io/modo-bugs/bugs.tsv", resource_id="bugged_cards_csv", can_304=True)
    if text is None:
        return None
    lines = [l.split('\t') for l in text.split('\n')]
    return lines[1:-1]

def time(q):
    url = 'http://maps.googleapis.com/maps/api/geocode/json?address={q}&sensor=false'.format(q=internal.escape(q))
    info = internal.fetch_json(url)
    try:
        location = info['results'][0]['geometry']['location']
    except IndexError:
        return 'Location unknown.'
    url = 'https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&sensor=false'.format(lat=internal.escape(str(location['lat'])), lng=internal.escape(str(location['lng'])), timestamp=internal.escape(str(dtutil.dt2ts(dtutil.now()))))
    timezone_info = internal.fetch_json(url)
    tz = timezone(timezone_info['timeZoneId'])
    return datetime.now(tz).strftime('%l:%M %p')
