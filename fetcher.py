import json
import os
import shutil
import urllib.request
import zipfile

import pkg_resources

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
    if os.path.isdir('./ziptemp'):
        shutil.rmtree('./ziptemp')
    os.mkdir('./ziptemp')
    store('https://mtgjson.com/json/AllCards.json.zip', './ziptemp/AllCards.json.zip')
    allcards_zip = zipfile.ZipFile('./ziptemp/AllCards.json.zip', 'r')
    allcards_zip.extractall('./ziptemp/unzip')
    allcards_zip.close()
    allcards_json = json.load(open('./ziptemp/unzip/AllCards.json', encoding='utf-8'))
    shutil.rmtree('./ziptemp')
    return allcards_json

def fetch(url, character_encoding='utf-8'):
    print("Fetching {0}".format(url))
    try:
        return urllib.request.urlopen(url).read().decode(character_encoding)
    except urllib.error.HTTPError as e:
        raise FetchException(e)

def store(url, path):
    print("Storing {0} in {1}".format(url, path))
    try:
        return urllib.request.urlretrieve(url, path)
    except urllib.error.HTTPError as e:
        raise FetchException(e)


class FetchException(Exception):
    pass

