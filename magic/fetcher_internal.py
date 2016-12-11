import json
import os
import shutil
import urllib.request
import zipfile
from email.utils import formatdate

import requests

from magic import database
from shared import configuration
from shared.pd_exception import OperationalException

SESSION = requests.Session()

def unzip(url, path):
    location = '{scratch_dir}/zip'.format(scratch_dir=configuration.get('scratch_dir'))
    shutil.rmtree(location, True)
    os.mkdir(location)
    store(url, '{location}/zip.zip'.format(location=location))
    f = zipfile.ZipFile('{location}/zip.zip'.format(location=location), 'r')
    f.extractall('{location}/unzip'.format(location=location))
    f.close()
    s = open('{location}/unzip/{path}'.format(location=location, path=path), encoding='utf-8').read()
    shutil.rmtree(location)
    return s

def fetch(url, character_encoding=None, resource_id=None):
    if_modified_since = None
    if resource_id is None:
        resource_id = url
    if_modified_since = get_last_modified(resource_id)
    print('Fetching {url} (Last Modified={when})'.format(url=url, when=if_modified_since))
    try:
        headers = {}
        if if_modified_since != None:
            headers["If-Modified-Since"] = if_modified_since
        response = SESSION.get(url, headers=headers)
        if character_encoding != None:
            response.encoding = character_encoding
        if response.status_code == 304:
            return get_cached_text(resource_id)
        last_modified = response.headers.get("Last-Modified")
        set_last_modified(resource_id, last_modified, response.text)
        return response.text
    except urllib.error.HTTPError as e:
        raise FetchException(e)
    except requests.exceptions.ConnectionError as e:
        cache = get_cached_text(resource_id)
        if cache is not None:
            print("Connection error: {}".format(e))
            print("Used cached value")
            return cache
        raise FetchException(e)

def fetch_json(url, character_encoding=None, resource_id=None):
    return json.loads(fetch(url, character_encoding, resource_id))

def post(url, data):
    print('POSTing to {url} with {data}'.format(url=url, data=data))
    try:
        response = SESSION.post(url, data=data)
        return response.text
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

def set_last_modified(resource, httptime=None, content=None):
    if httptime is None:
        httptime = formatdate(timeval=None, localtime=False, usegmt=True)
    database.DATABASE.execute("INSERT INTO fetcher (resource, last_modified, content) VALUES (?, ?, ?)", [resource, httptime, content])

def remove_last_modified(resource):
    database.DATABASE.execute("DELETE FROM fetcher WHERE resource = ?", [resource])


def get_cached_text(resource):
    return database.DATABASE.value("SELECT content FROM fetcher WHERE resource = ?", [resource])

class FetchException(OperationalException):
    pass

def acceptable_file(filepath: str) -> bool:
    # "This site is temporarily down because Wizards of the Coast sent me a DMCA notice." is 83 bytes.
    return os.path.isfile(filepath) and os.path.getsize(filepath) > 85

def escape(str_input) -> str:
    # Expand 'AE' into two characters. This matches the legal list and
    # WotC's naming scheme in Kaladesh, and is compatible with the
    # image server and magidex.
    return '+'.join(urllib.parse.quote(cardname.replace(u'Æ', 'AE')) for cardname in str_input.split(' ')).lower()
