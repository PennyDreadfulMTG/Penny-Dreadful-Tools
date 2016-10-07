import csv
import json
import os
import shutil
import urllib.request
import zipfile
from email.utils import formatdate

import pkg_resources
import requests

import configuration
import database

DATABASE = database.Database()

def legal_cards(force=False):
    lm = last_modified('legal_cards')
    if force:
        lm = None
    value = [s.lower() for s in fetch('http://pdmtgo.com/legal_cards.txt', 'latin-1', lm).split('\n')]
    set_last_modified('legal_cards')
    return value

def version():
    return pkg_resources.parse_version(json.loads(fetch('https://mtgjson.com/json/version.json')))

def mtgo_status():
    try:
        return json.loads(fetch('https://magic.wizards.com/sites/all/modules/custom/wiz_services/mtgo_status.php'))['status']
    except (FetchException, json.decoder.JSONDecodeError):
        return 'UNKNOWN'

def all_cards():
    s = unzip('https://mtgjson.com/json/AllCards.json.zip', 'AllCards.json')
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

def fetch(url, character_encoding=None, if_modified_since=None):
    print('Fetching {url}'.format(url=url))
    try:
        headers = {}
        if if_modified_since != None:
            headers["If-Modified-Since"] = if_modified_since
        response = requests.get(url, headers=headers)
        if character_encoding != None:
            response.encoding = character_encoding
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

def last_modified(resource):
    return DATABASE.value("SELECT last_modified FROM fetcher WHERE resource = ?", [resource])

def set_last_modified(resource):
    httptime = formatdate(timeval=None, localtime=False, usegmt=True)
    DATABASE.execute("INSERT INTO fetcher (resource, last_modified) VALUES (?, ?)", [resource, httptime])

def whatsinstandard():
    return json.loads(fetch('http://whatsinstandard.com/api/4/sets.json'))

class FetchException(Exception):
    pass
