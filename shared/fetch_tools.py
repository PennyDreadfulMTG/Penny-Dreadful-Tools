from decksite.scrapers.tappedout import SESSION
import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

import aiohttp
import requests

from shared import perf
from shared.pd_exception import OperationalException

def fetch(url: str, character_encoding: Optional[str] = None, force: bool = False, retry: bool = False, session: Optional[requests.Session] = None) -> str:
    headers = {}
    if force:
        headers['Cache-Control'] = 'no-cache'
    print('Fetching {url} ({cache})'.format(url=url, cache='no cache' if force else 'cache ok'))
    try:
        p = perf.start()
        if session is not None:
            response = SESSION.get(url, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        perf.check(p, 'slow_fetch', (url, headers), 'fetch')
        if character_encoding is not None:
            response.encoding = character_encoding
        if response.status_code in [500, 502, 503]:
            raise FetchException(f'Server returned a {response.status_code} from {url}')
        p = perf.start()
        t = response.text
        took = round(perf.took(p), 2)
        if took > 1:
            print('Getting text from response was very slow. Setting an explicit character_encoding may help.')
        return t
    except (urllib.error.HTTPError, requests.exceptions.ConnectionError, TimeoutError) as e: # type: ignore # urllib isn't fully stubbed
        if retry:
            return fetch(url, character_encoding, force, retry=False)
        raise FetchException(e) from e

async def fetch_async(url: str) -> str:
    print(f'Async fetching {url}')
    try:
        async with aiohttp.ClientSession() as aios:
            response = await aios.get(url)
            return await response.text()
    except (urllib.error.HTTPError, requests.exceptions.ConnectionError) as e: # type: ignore # urllib isn't fully stubbed
        raise FetchException(e) from e

def fetch_json(url: str, character_encoding: Optional[str] = None, session: Optional[requests.Session] = None) -> Any:
    try:
        blob = fetch(url, character_encoding, session=session)
        if blob:
            return json.loads(blob)
        return None
    except json.decoder.JSONDecodeError as e:
        print('Failed to load JSON:\n{0}'.format(blob))
        raise FetchException(e) from e

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
        response = requests.post(url, data=data, json=json_data)
        return response.text
    except requests.exceptions.ConnectionError as e:
        raise FetchException(e) from e

def store(url: str, path: str) -> requests.Response:
    print('Storing {url} in {path}'.format(url=url, path=path))
    try:
        response = requests.get(url, stream=True)
        with open(path, 'wb') as fout:
            for chunk in response.iter_content(1024):
                fout.write(chunk)
        return response
    except urllib.error.HTTPError as e: # type: ignore
        raise FetchException(e) from e
    except requests.exceptions.ConnectionError as e: # type: ignore
        raise FetchException(e) from e


async def store_async(url: str, path: str) -> aiohttp.ClientResponse:
    print('Async storing {url} in {path}'.format(url=url, path=path))
    try:
        async with aiohttp.ClientSession() as aios:
            response = await aios.get(url)
            with open(path, 'wb') as fout:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    fout.write(chunk)
            return response
    # type: ignore # urllib isn't fully stubbed
    except (urllib.error.HTTPError, aiohttp.ClientError) as e:
        raise FetchException(e) from e

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

#pylint: disable=R0913
def post_discord_webhook(webhook_id: str,
                         webhook_token: str,
                         message: Optional[str] = None,
                         username: str = None,
                         avatar_url: str = None,
                         embeds: List[Dict[str, Any]] = None
                         ) -> bool:
    if webhook_id is None or webhook_token is None:
        return False
    url = 'https://discordapp.com/api/webhooks/{id}/{token}'.format(
        id=webhook_id, token=webhook_token)
    post(url, json_data={
        'content': message,
        'username': username,
        'avatar_url': avatar_url,
        'embeds': embeds,
    })
    return True
