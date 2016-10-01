import csv
import json
import os
import shutil
import urllib.request
import zipfile

import pkg_resources

import configuration

def legal_cards():
    return [s.lower() for s in fetch('http://pdmtgo.com/legal_cards.txt', 'latin-1').split('\n')]

def version():
    return pkg_resources.parse_version(json.loads(fetch('https://mtgjson.com/json/version.json')))

def mtgo_status():
    try:
        return json.loads(fetch('https://magic.wizards.com/sites/all/modules/custom/wiz_services/mtgo_status.php'))['status']
    except (FetchException, json.decoder.JSONDecodeError):
        return 'UNKNOWN'

def all_cards():
    s = unzip('https://mtgjson.com/json/AllCards.json.zip', 'AllCards.json')
    return json.load(s)

def all_sets():
    s = unzip('https://mtgjson.com/json/AllSets.json.zip', 'AllSets.json')
    return json.load(s)

def unzip(url, path):
    if os.path.isdir('./ziptemp'):
        shutil.rmtree('./ziptemp')
    os.mkdir('./ziptemp')
    store(url, './ziptemp/zip.zip')
    f = zipfile.ZipFile('./ziptemp/zip.zip', 'r')
    f.extractall('./ziptemp/unzip')
    f.close()
    s = open('./ziptemp/unzip/{path}'.format(path=path), encoding='utf-8')
    shutil.rmtree('./ziptemp')
    return s

def card_aliases():
    with open(configuration.get('card_alias_file'), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))

def fetch(url, character_encoding='utf-8'):
    print('Fetching {url}'.format(url=url))
    try:
        return urllib.request.urlopen(url).read().decode(character_encoding)
    except urllib.error.HTTPError as e:
        raise FetchException(e)

def store(url, path):
    print('Storing {url} in {path}'.format(url=url, path=path))
    try:
        return urllib.request.urlretrieve(url, path)
    except urllib.error.HTTPError as e:
        raise FetchException(e)


class FetchException(Exception):
    pass
