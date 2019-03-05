import json
import os
import urllib.request
from typing import Any, Dict, Optional

import aiohttp
import requests
from cachecontrol import CacheControl, CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.heuristics import ExpiresAfter

from shared import configuration, perf
from shared.pd_exception import OperationalException

SESSION = CacheControl(requests.Session(),
                       cache=FileCache(configuration.get('web_cache')))
SESSION.mount(
    'http://whatsinstandard.com',
    CacheControlAdapter(heuristic=ExpiresAfter(days=14)))

def fetch(url: str, character_encoding: Optional[str] = None, force: bool = False, retry: bool = False) -> str:
    headers = {}
    if force:
        headers['Cache-Control'] = 'no-cache'
    print('Fetching {url} ({cache})'.format(url=url, cache='no cache' if force else 'cache ok'))
    try:
        p = perf.start()
        response = SESSION.get(url, headers=headers)
        perf.check(p, 'slow_fetch', (url, headers), 'fetch')
        if character_encoding is not None:
            response.encoding = character_encoding
        if response.status_code in [500, 502, 503]:
            raise FetchException(f'Server returned a {response.status_code}')
        p = perf.start()
        t = response.text
        took = round(perf.took(p), 2)
        if took > 1:
            print('Getting text from response was very slow. Setting an explicit character_encoding may help.')
        return t
    except (urllib.error.HTTPError, requests.exceptions.ConnectionError) as e: # type: ignore # urllib isn't fully stubbed
        if retry:
            return fetch(url, character_encoding, force, retry=False)
        raise FetchException(e)

async def fetch_async(url: str) -> str:
    print(f'Async fetching {url}')
    try:
        async with aiohttp.ClientSession() as aios:
            response = await aios.get(url)
            return await response.text()
    except (urllib.error.HTTPError, requests.exceptions.ConnectionError) as e: # type: ignore # urllib isn't fully stubbed
        raise FetchException(e)

def fetch_json(url: str, character_encoding: str = None) -> Any:
    try:
        blob = fetch(url, character_encoding)
        if blob:
            return json.loads(blob)
        return None
    except json.decoder.JSONDecodeError as e:
        print('Failed to load JSON:\n{0}'.format(blob))
        raise FetchException(e)

async def fetch_json_async(url: str) -> Any:
    try:
        blob = await fetch_async(url)
        if blob:
            return json.loads(blob)
        return None
    except json.decoder.JSONDecodeError:
        print('Failed to load JSON:\n{0}'.format(blob))
        raise

def post(url: str,
         data: Optional[Dict[str, str]] = None,
         json_data: Any = None
        ) -> str:
    print('POSTing to {url} with {data} / {json_data}'.format(url=url, data=data, json_data=json_data))
    try:
        response = SESSION.post(url, data=data, json=json_data)
        return response.text
    except requests.exceptions.ConnectionError as e:
        raise FetchException(e)

def store(url: str, path: str) -> requests.Response:
    print('Storing {url} in {path}'.format(url=url, path=path))
    try:
        response = requests.get(url, stream=True)
        with open(path, 'wb') as fout:
            for chunk in response.iter_content(1024):
                fout.write(chunk)
        return response
    except urllib.error.HTTPError as e: # type: ignore
        raise FetchException(e)

class FetchException(OperationalException):
    pass

def acceptable_file(filepath: str) -> bool:
    return os.path.isfile(filepath) and os.path.getsize(filepath) > 1000

def escape(str_input: str, skip_double_slash: bool = False) -> str:
    # Expand 'AE' into two characters. This matches the legal list and
    # WotC's naming scheme in Kaladesh, and is compatible with the
    # image server and scryfall.
    s = str_input
    if skip_double_slash:
        s = s.replace('//', '-split-')
    s = urllib.parse.quote_plus(s.replace(u'Æ', 'AE')).lower() # type: ignore # urllib isn't fully stubbed
    if skip_double_slash:
        s = s.replace('-split-', '//')
    return s
