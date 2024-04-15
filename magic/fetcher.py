"""
Helper methods for fetching resources.
This is the High-Level equivelent of shared.fetch_tools
"""
import csv
import datetime
import functools
import json
import os
import re
from collections import OrderedDict
from time import sleep
from typing import Any, Literal, TypedDict, cast
from urllib import parse

import feedparser
import pytz

from magic import layout
from magic.abc import CardDescription, PriceDataType
from magic.models import Deck
from shared import configuration, dtutil, fetch_tools
from shared import redis_wrapper as redis
from shared.container import Container
from shared.fetch_tools import FetchException
from shared.pd_exception import (InvalidArgumentException, InvalidDataException,
                                 NotConfiguredException, TooFewItemsException)
from shared.types import BugData, ForumData


async def achievement_cache_async() -> dict[str, dict[str, str]]:
    data = await fetch_tools.fetch_json_async(decksite_url('/api/achievements'))
    return {a['key']: a for a in data['achievements']}

async def all_cards_async(force_last_good: bool = False) -> tuple[list[CardDescription], str]:
    download_uri = await bulk_data_uri()
    if force_last_good:
        response = None
    else:
        response = await fetch_tools.fetch_json_async(download_uri)
    if not isinstance(response, list):
        try:
            backup = configuration.last_good_bulk_data.value
            return await fetch_tools.fetch_json_async(backup), backup
        except Exception as c:
            raise FetchException(f'Default Cards not in expected format. Got {response}') from c
    return response, download_uri

async def all_sets_async() -> list[dict[str, Any]]:
    try:
        d = json.load(open('sets.json'))
    except FileNotFoundError:
        d = await fetch_tools.fetch_json_async('https://api.scryfall.com/sets')
    assert not d['has_more']
    return d['data']

async def banner_cards() -> tuple[list[str], str]:
    data = await fetch_tools.fetch_json_async(decksite_url('/api/banner'))
    return (data['cardnames'], data['background'])

async def bulk_data_uri() -> str:
    endpoints = await fetch_tools.fetch_json_async('https://api.scryfall.com/bulk-data')
    for e in endpoints['data']:
        if e['type'] == 'default_cards':
            return e['download_uri']
    else:
        raise FetchException('Unable to find Default Cards')

async def bugged_cards_async() -> list[BugData] | None:
    try:
        bugs = fetch_tools.fetch_json('https://pennydreadfulmtg.github.io/modo-bugs/bugs.json')
    except FetchException:
        print("WARNING: Couldn't fetch bugs")
        bugs = None
    return bugs

def card_aliases() -> list[list[str]]:
    with open(configuration.card_alias_file.get(), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))

def card_price(cardname: str) -> PriceDataType:
    return fetch_tools.fetch_json('http://vorpald20.com:5800/{}/'.format(cardname.replace('//', '-split-')))

def current_time(timezone: datetime.tzinfo, twentyfour: bool) -> str:
    if twentyfour:
        return dtutil.now(timezone).strftime('%H:%M')
    try:
        return dtutil.now(timezone).strftime('%l:%M %p')
    except ValueError:  # %l is not a univerally supported argument.  Fall back to %I on other platforms.
        return dtutil.now(timezone).strftime('%I:%M %p')

async def daybreak_forums_async() -> dict[str, ForumData] | None:
    try:
        bugs = fetch_tools.fetch_json('https://pennydreadfulmtg.github.io/modo-bugs/forums.json')
    except FetchException:
        print("WARNING: Couldn't fetch forums")
        bugs = None
    return bugs

def decksite_url(path: str = '/') -> str:
    return site_url(configuration.get_str('decksite_protocol'), configuration.get_str('decksite_hostname'), configuration.get_int('decksite_port'), path)

def logsite_url(path: str = '/') -> str:
    return site_url(configuration.get_str('logsite_protocol'), configuration.get_str('logsite_hostname'), configuration.get_int('logsite_port'), path)

def site_url(protocol: str, hostname: str, port: int, path: str) -> str:
    if port != 80:
        base = f'{hostname}:{port}'
    else:
        base = hostname
    url = parse.urlunparse((protocol, base, path, '', '', ''))
    assert url is not None
    return url

def downtimes() -> str:
    return fetch_tools.fetch('https://pennydreadfulmtg.github.io/modo-bugs/downtimes.txt')

def gatherling_deck_comments(d: Deck) -> list[str]:
    url = f'http://gatherling.com/deck.php?mode=view&id={d.identifier}'
    s = fetch_tools.fetch(url)
    result = re.search('COMMENTS</td></tr><tr><td>(.*)</td></tr></table></div><div class="clear"></div><center>', s, re.MULTILINE | re.DOTALL)
    if result:
        return result.group(1).replace('<br />', '\n').split('\n')
    return []

async def gatherling_whois(name: str | None = None, discord_id: str | None = None) -> Container:
    if discord_id:
        url = f'https://gatherling.com/api.php?action=whois&discordid={discord_id}'
    elif name:
        url = f'https://gatherling.com/api.php?action=whois&name={name}'
    else:
        raise InvalidArgumentException('No identifier provided')
    data = await fetch_tools.fetch_json_async(url)
    return Container(data)

async def gatherling_active_events() -> list[Container]:
    url = 'https://gatherling.com/api.php?action=active_events'
    data: dict = await fetch_tools.fetch_json_async(url)
    return [Container(d) for d in data.values()]

def hq_artcrops() -> dict[str, tuple[str, int]]:
    with open('hq_artcrops.json') as f:
        return json.load(f)


if configuration.production.value:
    hq_artcrops = functools.lru_cache(hq_artcrops)  # These won't be changing in production, so avoid the IO cost of reading the file every time.

async def legal_cards_async(season: str | None = None) -> list[str]:
    if season is None:
        url = 'legal_cards.txt'
    else:
        url = f'{season}_legal_cards.txt'
    encoding = 'utf-8'
    cached_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'legal_cards')
    if os.path.exists(os.path.join(cached_path, url)):
        h = open(os.path.join(cached_path, url), encoding=encoding)
        legal = h.readlines()
        h.close()
        return [card.strip() for card in legal]

    url = 'https://pennydreadfulmtg.github.io/' + url
    legal_txt = await fetch_tools.fetch_async(url)
    if legal_txt.startswith('<!DOCTYPE html>'):
        return []
    return legal_txt.strip().split('\n')

async def mtgo_status() -> str:
    try:
        data = await fetch_tools.fetch_json_async('https://census.daybreakgames.com/s:example/get/global/game_server_status?game_code=mtgo&c:limit=1000')
        last_reported_state = data['game_server_status_list'][0]['last_reported_state']
        return 'UP' if last_reported_state in ['high', 'medium', 'low'] else last_reported_state
    except (FetchException, json.decoder.JSONDecodeError):
        return 'UNKNOWN'

async def person_data_async(person: str | int) -> dict[str, Any]:
    try:
        data = await fetch_tools.fetch_json_async(decksite_url(f'/api/person/{person}'))
    except (FetchException, json.decoder.JSONDecodeError):
        return {}
    return data

def resources() -> dict[str, dict[str, str]]:
    with open('decksite/resources.json', encoding='utf-8') as resources_file:
        return json.load(resources_file, object_pairs_hook=OrderedDict)

async def scryfall_last_updated_async() -> datetime.datetime:
    try:
        d = await fetch_tools.fetch_json_async('https://api.scryfall.com/bulk-data')
        for o in d['data']:
            if o['type'] == 'default_cards':
                return dtutil.parse_rfc3339(o['updated_at'])
    except json.JSONDecodeError as e:
        raise InvalidDataException('Scryfall data is not JSON') from e
    raise InvalidDataException(f'Could not get the last updated date from Scryfall: {d}')

def search_scryfall(query: str, exhaustive: bool = False) -> tuple[int, list[str], list[CardDescription]]:
    """Returns a tuple. First member is an integer indicating how many cards match the query total,
       second member is a list of card names up to the maximum that could be fetched in a timely fashion.
       third member is a list of the full card data of said cards.
       Supply exhaustive=True to instead retrieve the full list (potentially very slow)."""
    if query == '':
        return False, [], []
    redis_key = f'scryfall:query:{query}:' + ('exhaustive' if exhaustive else 'nonexhaustive')
    cached = redis.get_list(redis_key)
    result_data: list[CardDescription]
    if cached:
        total_cards, result_data = int(cached[0]), cached[1]
    else:
        url = 'https://api.scryfall.com/cards/search?q=' + fetch_tools.escape(query)
        result_data = []
        while True:
            for _ in range(3):
                try:
                    result_json = fetch_tools.fetch_json(url)
                    break
                except FetchException as c:
                    print(c)
            if 'code' in result_json.keys():  # The API returned an error
                if result_json['status'] == 404:  # No cards found
                    return False, [], []
                print('Error fetching scryfall data:\n', result_json)
                return False, [], []
            for warning in result_json.get('warnings', []):  # scryfall-provided human-readable warnings
                print(warning)  # Why aren't we displaying these to the user?
            result_data += result_json['data']
            total_cards = int(result_json['total_cards'])
            if not exhaustive or len(result_data) >= total_cards:
                break
            sleep(0.1)
            url = result_json['next_page']
        redis.store(redis_key, [total_cards, result_data], ex=3600)
    result_data.sort(key=lambda x: x['legalities']['penny'])

    def get_frontside(scr_card: CardDescription) -> str:
        """If card is transform, returns first name. Otherwise, returns name.
        This is to make sure cards are later found in the database"""
        if scr_card['layout'] in layout.has_two_names() and not scr_card['layout'] in layout.uses_two_names() and not scr_card['layout'] in layout.has_meld_back():
            return scr_card['card_faces'][0]['name']
        return scr_card['name']
    result_cardnames = [get_frontside(obj) for obj in result_data]
    return total_cards, result_cardnames, result_data

async def dreadrise_count_cards(query: str) -> tuple[int, str | None]:
    """
        If the search succeeds, returns the number of results.
        If it doesn't, returns -1 and the error given by the engine.
    """
    domain = configuration.get_str('dreadrise_url')
    query = fetch_tools.escape(query)
    url = f'{domain}/cards/find?q={query}+output:resultcount'
    count_txt = await fetch_tools.fetch_async(url)
    try:
        return int(count_txt), None  # if this fails, the query errored
    except ValueError:
        return -1, count_txt

async def dreadrise_search_json(url: str, page_size: int = 60, **kwargs: Any) -> dict:
    kwargs['page'] = 0
    kwargs['page_size'] = page_size
    domain = configuration.get_str('dreadrise_url')
    pd = '?dist=penny_dreadful'
    try:
        data = await fetch_tools.post_json_async(domain + url + pd, kwargs)
        if 'success' not in data:
            raise InvalidDataException('Invalid JSON signature!')
        return cast(dict, data)
    except (fetch_tools.FetchException, json.JSONDecodeError, InvalidDataException) as e:
        print(f'Error while fetching from {url}:', e)
        return {'success': False, 'reason': 'The request failed.'}

async def dreadrise_search_cards(query: str, page_size: int = 60, pd_mode: Literal[1, 0, -1] = 0) -> dict:
    """
        pd_mode can be -1 (illegal in pd), 0 (doesn't matter if is legal in pd), and 1 (must be legal in pd).
        returns the list of found cards.
    """
    if pd_mode != 0:
        minus = '-' if pd_mode < 0 else ''
        query = f'{minus}f:pd ({query})'
    return await dreadrise_search_json('/api/card-search/cards', page_size, query=query)

async def dreadrise_search_decks(query: str, max_decks: int) -> dict:
    return await dreadrise_search_json('/api/deck-search/decks', max_decks, query=query)

async def dreadrise_search_matchups(q1: str, q2: str, max_count: int) -> dict:
    return await dreadrise_search_json('/api/deck-search/matchups', max_count, q1=q1, q2=q2)

def rulings(cardname: str) -> list[dict[str, str]]:
    card = fetch_tools.fetch_json(f'https://api.scryfall.com/cards/named?exact={cardname}')
    return fetch_tools.fetch_json(card['uri'] + '/rulings')['data']

def sitemap() -> list[str]:
    cached = redis.get_list('magic:fetcher:sitemap')
    if cached is not None:
        return cached
    d = fetch_tools.fetch_json(decksite_url('/api/sitemap/'))
    if d is None:
        raise FetchException('Unable to retrieve sitemap')
    sm = d['urls']
    redis.store('magic:fetcher:sitemap', sm, ex=300)
    return sm

def subreddit() -> Container:
    url = 'https://www.reddit.com/r/pennydreadfulMTG/.rss'
    return feedparser.parse(url)

def time(q: str, twentyfour: bool) -> dict[str, list[str]]:
    return times_from_timezone_code(q, twentyfour) if len(q) <= 4 else times_from_location(q, twentyfour)

def times_from_timezone_code(q: str, twentyfour: bool) -> dict[str, list[str]]:
    possibles = list(filter(lambda x: datetime.datetime.now(pytz.timezone(x)).strftime('%Z') == q.upper(), pytz.common_timezones))
    if not possibles:
        raise TooFewItemsException(f'Not a recognized timezone: {q.upper()}')
    results: dict[str, list[str]] = {}
    for possible in possibles:
        timezone = dtutil.timezone(possible)
        t = current_time(timezone, twentyfour)
        results[t] = results.get(t, []) + [possible]
    return results

def times_from_location(q: str, twentyfour: bool) -> dict[str, list[str]]:
    api_key = configuration.get('google_maps_api_key')
    if not api_key:
        raise NotConfiguredException('No value found for google_maps_api_key')
    url = f'https://maps.googleapis.com/maps/api/geocode/json?address={fetch_tools.escape(q)}&key={api_key}&sensor=false'
    info = fetch_tools.fetch_json(url)
    if 'error_message' in info:
        return info['error_message']
    try:
        location = info['results'][0]['geometry']['location']
    except IndexError as e:
        raise TooFewItemsException(e) from e
    url = 'https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&key={api_key}&sensor=false'.format(lat=fetch_tools.escape(str(location['lat'])), lng=fetch_tools.escape(str(location['lng'])), timestamp=fetch_tools.escape(str(dtutil.dt2ts(dtutil.now()))), api_key=api_key)
    timezone_info = fetch_tools.fetch_json(url)
    if 'error_message' in timezone_info:
        return timezone_info['error_message']
    if timezone_info['status'] == 'ZERO_RESULTS':
        raise TooFewItemsException(timezone_info['status'])
    try:
        timezone = dtutil.timezone(timezone_info['timeZoneId'])
    except KeyError as e:
        raise TooFewItemsException(f'Unable to find a timezone in {timezone_info}') from e
    return {current_time(timezone, twentyfour): [info['results'][0]['formatted_address']]}


class WISDateType(TypedDict):
    exact: str
    rough: str

class WISSetInfoType(TypedDict):
    name: str
    code: str
    codename: str
    mtgoCode: str
    symbol: str
    enterDate: WISDateType
    exitDate: WISDateType

class WISSchemaType(TypedDict):
    deprecated: bool
    sets: list[WISSetInfoType]

def whatsinstandard() -> WISSchemaType:
    # if you're here to hack data because WIS isn't correct, use magic.seasons.OVERRIDES instead
    cached = redis.get_container('magic:fetcher:whatisinstandard_6')
    if cached is not None:
        return cached

    try:
        info = fetch_tools.fetch_json('http://whatsinstandard.com/api/v6/standard.json')
    except FetchException:
        cached = redis.get_container('magic:fetcher:whatisinstandard_noex')
        if cached is not None:
            return cached
        raise

    redis.store('magic:fetcher:whatisinstandard_6', info, ex=86400)
    redis.store('magic:fetcher:whatisinstandard_noex', info)
    return info
