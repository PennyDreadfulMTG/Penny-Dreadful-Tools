import csv
import datetime
import json
import os
import re
from collections import OrderedDict
from time import sleep
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from urllib import parse

import feedparser
import pytz

import shared.fetcher_internal as internal
from magic.card_description import CardDescription
from magic.models import Card, Deck
from shared import configuration, dtutil, redis
from shared.container import Container
from shared.fetcher_internal import FetchException
from shared.pd_exception import (InvalidDataException, NotConfiguredException,
                                 TooFewItemsException)


async def achievement_cache_async() -> Dict[str, Dict[str, str]]:
    data = await internal.fetch_json_async(decksite_url('/api/achievements'))
    return {a['key']: a for a in data['achievements']}

def all_cards() -> List[CardDescription]:
    try:
        f = open('all-default-cards.json')
        return json.load(f)
    except FileNotFoundError:
        return internal.fetch_json('https://archive.scryfall.com/json/scryfall-default-cards.json', character_encoding='utf-8')

def all_sets() -> List[Dict[str, Any]]:
    try:
        d = json.load(open('sets.json'))
    except FileNotFoundError:
        d = internal.fetch_json('https://api.scryfall.com/sets')
    assert not d['has_more']
    return d['data']

def bugged_cards() -> Optional[List[Dict[str, Any]]]:
    try:
        bugs = internal.fetch_json('https://pennydreadfulmtg.github.io/modo-bugs/bugs.json')
    except FetchException:
        print("WARNING: Couldn't fetch bugs")
        bugs = None
    if bugs is None:
        return None
    return bugs

def card_aliases() -> List[List[str]]:
    with open(configuration.get_str('card_alias_file'), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))

def card_price(cardname: str) -> Dict[str, Any]:
    return internal.fetch_json('http://vorpald20.com:5800/{0}/'.format(cardname.replace('//', '-split-')))

def card_price_string(card: Card, short: bool = False) -> str:
    def price_info(c: Card) -> str:
        try:
            p = card_price(c.name)
        except FetchException:
            return 'Price unavailable'
        if p is None:
            return 'Not available online'
        # Currently disabled
        s = '{price}'.format(price=format_price(p['price']))
        if float(p['low']) <= 0.05:
            s += ' (low {low}, high {high}'.format(low=format_price(p['low']), high=format_price(p['high']))
            if float(p['low']) <= 0.01 and not short:
                s += ', {week}% this week, {month}% this month, {season}% this season'.format(week=round(float(p['week']) * 100.0), month=round(float(p['month']) * 100.0), season=round(float(p['season']) * 100.0))
            s += ')'
        age = dtutil.dt2ts(dtutil.now()) - p['time']
        if age > 60 * 60 * 2:
            s += '\nWARNING: price information is {display} old'.format(display=dtutil.display_time(age, 1))
        return s
    def format_price(p: Optional[str]) -> str:
        if p is None:
            return 'Unknown'
        dollars, cents = str(round(float(p), 2)).split('.')
        return '{dollars}.{cents}'.format(dollars=dollars, cents=cents.ljust(2, '0'))
    return price_info(card)

def decksite_url(path: str = '/') -> str:
    hostname = configuration.get_str('decksite_hostname')
    port = configuration.get_int('decksite_port')
    if port != 80:
        hostname = '{hostname}:{port}'.format(hostname=hostname, port=port)
    url = parse.urlunparse((configuration.get_str('decksite_protocol'), hostname, path, '', '', ''))
    assert url is not None
    return url

def legal_cards(force: bool = False, season: str = None) -> List[str]:
    if season is None:
        url = 'legal_cards.txt'
    else:
        url = '{season}_legal_cards.txt'.format(season=season)
    encoding = 'utf-8' if season != 'EMN' else 'latin-1' # EMN was encoded weirdly.
    cached_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'legal_cards')
    if os.path.exists(os.path.join(cached_path, url)):
        h = open(os.path.join(cached_path, url), encoding=encoding)
        legal = h.readlines()
        h.close()
        return [l.strip() for l in legal]

    url = 'http://pdmtgo.com/' + url
    legal_txt = internal.fetch(url, encoding, force=force)
    if season is not None and configuration.get_bool('save_historic_legal_lists'):
        with open(os.path.join(cached_path, f'{season}_legal_cards.txt'), 'w', encoding=encoding) as h:
            h.write(legal_txt)

    return legal_txt.strip().split('\n')

def scryfall_last_updated() -> datetime.datetime:
    d = internal.fetch_json('https://api.scryfall.com/bulk-data')
    for o in d['data']:
        if o['type'] == 'default_cards':
            return dtutil.parse_rfc3339(o['updated_at'])
    raise InvalidDataException(f'Could not get the last updated date from Scryfall: {d}')

async def mtgo_status() -> str:
    try:
        return cast(str, (await internal.fetch_json_async('https://s3-us-west-2.amazonaws.com/s3-mtgo-greendot/status.json'))['status'])
    except (FetchException, json.decoder.JSONDecodeError):
        return 'UNKNOWN'

async def person_data_async(person: Union[str, int]) -> Dict[str, Any]:
    try:
        data = await internal.fetch_json_async(decksite_url('/api/person/{0}'.format(person)))
    except (FetchException, json.decoder.JSONDecodeError):
        return {}
    return data

def post_discord_webhook(webhook_id: str, webhook_token: str, message: str, name: str = None) -> bool:
    if webhook_id is None or webhook_token is None:
        return False
    url = 'https://discordapp.com/api/webhooks/{id}/{token}'.format(id=webhook_id, token=webhook_token)
    internal.post(url, json_data={
        'content': message,
        'username': name,
        })
    return True

# pylint: disable=unsubscriptable-object
def resources() -> Dict[str, Dict[str, str]]:
    with open('decksite/resources.json') as resources_file:
        return json.load(resources_file, object_pairs_hook=OrderedDict)

async def scryfall_cards_async() -> Dict[str, Any]:
    url = 'https://api.scryfall.com/cards'
    return await internal.fetch_json_async(url)

def search_scryfall(query: str, exhaustive: bool = False) -> Tuple[int, List[str]]:
    """Returns a tuple. First member is an integer indicating how many cards match the query total,
       second member is a list of card names up to the maximum that could be fetched in a timely fashion.
       Supply exhaustive=True to instead retrieve the full list (potentially very slow)."""
    if query == '':
        return False, []
    redis_key = f'scryfall:query:{query}:' + ('exhaustive' if exhaustive else 'nonexhaustive')
    cached = redis.get_list(redis_key)
    result_data: List[Dict]
    if cached:
        total_cards, result_data = int(cached[0]), cached[1]
    else:
        url = 'https://api.scryfall.com/cards/search?q=' + internal.escape(query)
        result_data = []
        while True:
            result_json = internal.fetch_json(url, character_encoding='utf-8')
            if 'code' in result_json.keys(): # The API returned an error
                if result_json['status'] == 404: # No cards found
                    return False, []
                print('Error fetching scryfall data:\n', result_json)
                return False, []
            for warning in result_json.get('warnings', []): #scryfall-provided human-readable warnings
                print(warning) # Why aren't we displaying these to the user?
            result_data += result_json['data']
            total_cards = int(result_json['total_cards'])
            if not exhaustive or len(result_data) >= total_cards:
                break
            sleep(0.1)
            url = result_json['next_page']
        redis.store(redis_key, [total_cards, result_data], ex=3600)
    result_data.sort(key=lambda x: x['legalities']['penny'])
    def get_frontside(scr_card: Dict) -> str:
        """If card is transform, returns first name. Otherwise, returns name.
        This is to make sure cards are later found in the database"""
        #not sure how to handle meld cards
        if scr_card['layout'] in ['transform', 'flip']:
            return scr_card['card_faces'][0]['name']
        return scr_card['name']
    result_cardnames = [get_frontside(obj) for obj in result_data]
    return total_cards, result_cardnames

def rulings(cardname: str) -> List[Dict[str, str]]:
    card = internal.fetch_json('https://api.scryfall.com/cards/named?exact={name}'.format(name=cardname))
    return internal.fetch_json(card['uri'] + '/rulings')['data']

def sitemap() -> List[str]:
    return internal.fetch_json(decksite_url('/api/sitemap/'))['urls']

def time(q: str, twentyfour: bool) -> Dict[str, List[str]]:
    return times_from_timezone_code(q, twentyfour) if len(q) <= 3 else times_from_location(q, twentyfour)

def times_from_timezone_code(q: str, twentyfour: bool) ->  Dict[str, List[str]]:
    possibles = list(filter(lambda x: datetime.datetime.now(pytz.timezone(x)).strftime('%Z') == q.upper(), pytz.common_timezones))
    if not possibles:
        raise TooFewItemsException(f'Not a recognized timezone: {q.upper()}')
    results: Dict[str, List[str]] = {}
    for possible in possibles:
        timezone = dtutil.timezone(possible)
        t = current_time(timezone, twentyfour)
        results[t] = results.get(t, []) + [possible]
    return results

def times_from_location(q: str, twentyfour: bool) -> Dict[str, List[str]]:
    api_key = configuration.get('google_maps_api_key')
    if not api_key:
        raise NotConfiguredException('No value found for google_maps_api_key')
    url = 'https://maps.googleapis.com/maps/api/geocode/json?address={q}&key={api_key}&sensor=false'.format(q=internal.escape(q), api_key=api_key)
    info = internal.fetch_json(url)
    if 'error_message' in info:
        return info['error_message']
    try:
        location = info['results'][0]['geometry']['location']
    except IndexError as e:
        raise TooFewItemsException(e)
    url = 'https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&key={api_key}&sensor=false'.format(lat=internal.escape(str(location['lat'])), lng=internal.escape(str(location['lng'])), timestamp=internal.escape(str(dtutil.dt2ts(dtutil.now()))), api_key=api_key)
    timezone_info = internal.fetch_json(url)
    if 'error_message' in timezone_info:
        return timezone_info['error_message']
    if timezone_info['status'] == 'ZERO_RESULTS':
        raise TooFewItemsException(timezone_info['status'])
    try:
        timezone = dtutil.timezone(timezone_info['timeZoneId'])
    except KeyError as e:
        raise TooFewItemsException(f'Unable to find a timezone in {timezone_info}')
    return {current_time(timezone, twentyfour): [q]}

def current_time(timezone: datetime.tzinfo, twentyfour: bool) -> str:
    if twentyfour:
        return dtutil.now(timezone).strftime('%H:%M')
    try:
        return dtutil.now(timezone).strftime('%l:%M %p')
    except ValueError: # %l is not a univerally supported argument.  Fall back to %I on other platforms.
        return dtutil.now(timezone).strftime('%I:%M %p')

def whatsinstandard() -> Dict[str, Union[bool, List[Dict[str, str]]]]:
    cached = redis.get_container('magic:fetcher:whatisinstandard')
    if cached is not None:
        return cached

    try:
        info = internal.fetch_json('http://whatsinstandard.com/api/v5/sets.json')
    except FetchException:
        cached = redis.get_container('magic:fetcher:whatisinstandard_noex')
        if cached is not None:
            return cached
        raise
    redis.store('magic:fetcher:whatisinstandard', info, ex=86400)
    redis.store('magic:fetcher:whatisinstandard_noex', info)
    return info

def subreddit() -> Container:
    url = 'https://www.reddit.com/r/pennydreadfulMTG/.rss'
    return feedparser.parse(url)

def gatherling_deck_comments(d: Deck) -> List[str]:
    url = f'http://gatherling.com/deck.php?mode=view&id={d.identifier}'
    s = internal.fetch(url)
    result = re.search('COMMENTS</td></tr><tr><td>(.*)</td></tr></table></div><div class="clear"></div><center>', s, re.MULTILINE | re.DOTALL)
    if result:
        return result.group(1).replace('<br />', '\n').split('\n')
    return []
