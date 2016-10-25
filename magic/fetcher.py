import csv
import json
import os
import shutil
import urllib.request
import zipfile
from email.utils import formatdate

import pkg_resources
import requests

from magic import configuration
from magic import database

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

def unzip(url, path):
    if os.path.isdir('./ziptemp'):
        shutil.rmtree('./ziptemp')
    os.mkdir('./ziptemp')
    store(url, './ziptemp/zip.zip')
    f = zipfile.ZipFile('./ziptemp/zip.zip', 'r')
    f.extractall('./ziptemp/unzip')
    f.close()
    s = open('./ziptemp/unzip/{path}'.format(path=path), encoding='utf-8').read()
    shutil.rmtree('./ziptemp')
    return s

def card_aliases():
    with open(configuration.get('card_alias_file'), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))

def fetch(url, character_encoding=None, resource_id=None):
    if_modified_since = None
    if resource_id is None:
        print('Fetching {url}'.format(url=url))
    else:
        if_modified_since = get_last_modified(resource_id)
        print('Fetching {url} (Last Modified={when})'.format(url=url, when=if_modified_since))
    try:
        headers = {}
        if if_modified_since != None:
            headers["If-Modified-Since"] = if_modified_since
        response = requests.get(url, headers=headers)
        if character_encoding != None:
            response.encoding = character_encoding
        last_modified = response.headers.get("Last-Modified")
        if resource_id is not None and last_modified is not None:
            set_last_modified(resource_id, last_modified)
        if response.status_code == 304:
            return '' # I wanted to return None, but that broke a surprising amount of things
        return response.text
    except urllib.error.HTTPError as e:
        raise FetchException(e)
    except requests.exceptions.ConnectionError as e:
        raise FetchException(e)

def store(url, path):
    print('Storing {url} in {path}'.format(url=url, path=path))
    try:
        return urllib.request.urlretrieve(url, path)
    except urllib.error.HTTPError as e:
        raise FetchException(e)

def get_last_modified(resource):
    return database.DATABASE.value("SELECT last_modified FROM fetcher WHERE resource = ?", [resource])

def set_last_modified(resource, httptime=None):
    if httptime is None:
        httptime = formatdate(timeval=None, localtime=False, usegmt=True)
    database.DATABASE.execute("INSERT INTO fetcher (resource, last_modified) VALUES (?, ?)", [resource, httptime])

def whatsinstandard():
    return json.loads(fetch('http://whatsinstandard.com/api/4/sets.json'))

def fetch_prices():
    store('http://magic.bluebones.net/prices.db', configuration.get('pricesdb'))

def card_price(cardname):
    return json.loads(fetch('http://magic.bluebones.net:5800/{0}/'.format(cardname)))

def resources():
    return json.loads(fetch('http://magic.bluebones.net/pd/resources.json'))

class FetchException(Exception):
    pass
