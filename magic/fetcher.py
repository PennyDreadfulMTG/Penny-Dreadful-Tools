"""
Helper methods for fetching resources.
This is the High-Level equivelent of shared.fetch_tools
"""
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
from mypy_extensions import TypedDict

from magic.abc import CardDescription, PriceDataType
from magic.models import Deck
from shared import configuration, dtutil, fetch_tools
from shared import redis_wrapper as redis
from shared.container import Container
from shared.fetch_tools import FetchException
from shared.pd_exception import (InvalidArgumentException, InvalidDataException,
                                 NotConfiguredException, TooFewItemsException)


async def achievement_cache_async() -> Dict[str, Dict[str, str]]:
    data = await fetch_tools.fetch_json_async(decksite_url('/api/achievements'))
    return {a['key']: a for a in data['achievements']}

async def all_cards_async() -> List[CardDescription]:
    try:
        f = open('scryfall-default-cards.json')
        return json.load(f)
    except FileNotFoundError as c:
        endpoints = await fetch_tools.fetch_json_async('https://api.scryfall.com/bulk-data')
        for e in endpoints['data']:
            if e['type'] == 'default_cards':
                return await fetch_tools.fetch_json_async(e['download_uri'])
        raise FetchException('Unable to find Default Cards') from c

async def all_sets_async() -> List[Dict[str, Any]]:
    try:
        d = json.load(open('sets.json'))
    except FileNotFoundError:
        d = await fetch_tools.fetch_json_async('https://api.scryfall.com/sets')
    assert not d['has_more']
    return d['data']

async def bugged_cards_async() -> Optional[List[Dict[str, Any]]]:
    try:
        bugs = fetch_tools.fetch_json('https://pennydreadfulmtg.github.io/modo-bugs/bugs.json')
    except FetchException:
        print("WARNING: Couldn't fetch bugs")
        bugs = None
    if bugs is None:
        return None
    return bugs

def card_aliases() -> List[List[str]]:
    with open(configuration.get_str('card_alias_file'), newline='', encoding='utf-8') as f:
        return list(csv.reader(f, dialect='excel-tab'))

def card_price(cardname: str) -> PriceDataType:
    return fetch_tools.fetch_json('http://vorpald20.com:5800/{0}/'.format(cardname.replace('//', '-split-')))

def current_time(timezone: datetime.tzinfo, twentyfour: bool) -> str:
    if twentyfour:
        return dtutil.now(timezone).strftime('%H:%M')
    try:
        return dtutil.now(timezone).strftime('%l:%M %p')
    except ValueError:  # %l is not a univerally supported argument.  Fall back to %I on other platforms.
        return dtutil.now(timezone).strftime('%I:%M %p')

def decksite_url(path: str = '/') -> str:
    return site_url(configuration.get_str('decksite_protocol'), configuration.get_str('decksite_hostname'), configuration.get_int('decksite_port'), path)

def logsite_url(path: str = '/') -> str:
    return site_url(configuration.get_str('logsite_protocol'), configuration.get_str('logsite_hostname'), configuration.get_int('logsite_port'), path)

def site_url(protocol: str, hostname: str, port: int, path: str) -> str:
    if port != 80:
        base = '{hostname}:{port}'.format(hostname=hostname, port=port)
    else:
        base = hostname
    url = parse.urlunparse((protocol, base, path, '', '', ''))
    assert url is not None
    return url

def downtimes() -> str:
    return fetch_tools.fetch('https://pennydreadfulmtg.github.io/modo-bugs/downtimes.txt')

def gatherling_deck_comments(d: Deck) -> List[str]:
    url = f'http://gatherling.com/deck.php?mode=view&id={d.identifier}'
    s = fetch_tools.fetch(url)
    result = re.search('COMMENTS</td></tr><tr><td>(.*)</td></tr></table></div><div class="clear"></div><center>', s, re.MULTILINE | re.DOTALL)
    if result:
        return result.group(1).replace('<br />', '\n').split('\n')
    return []

async def gatherling_whois(name: Optional[str] = None, discord_id: Optional[str] = None) -> Container:
    if discord_id:
        url = f'https://gatherling.com/api.php?action=whois&discordid={discord_id}'
    elif name:
        url = f'https://gatherling.com/api.php?action=whois&name={name}'
    else:
        raise InvalidArgumentException('No identifier provided')
    data = await fetch_tools.fetch_json_async(url)
    return Container(data)
async def legal_cards_async(season: str = None) -> List[str]:
    if season is None:
        url = 'legal_cards.txt'
    else:
        url = '{season}_legal_cards.txt'.format(season=season)
    encoding = 'utf-8'
    cached_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'legal_cards')
    if os.path.exists(os.path.join(cached_path, url)):
        h = open(os.path.join(cached_path, url), encoding=encoding)
        legal = h.readlines()
        h.close()
        return [card.strip() for card in legal]

    url = 'https://pennydreadfulmtg.github.io/' + url
    legal_txt = await fetch_tools.fetch_async(url)
    if season is not None and configuration.get_bool('save_historic_legal_lists'):
        with open(os.path.join(cached_path, f'{season}_legal_cards.txt'), 'w', encoding=encoding) as h:
            h.write(legal_txt)

    return legal_txt.strip().split('\n')

async def mtgo_status() -> str:
    try:
        return cast(str, (await fetch_tools.fetch_json_async('https://s3-us-west-2.amazonaws.com/s3-mtgo-greendot/status.json'))['status'])
    except (FetchException, json.decoder.JSONDecodeError):
        return 'UNKNOWN'

async def person_data_async(person: Union[str, int]) -> Dict[str, Any]:
    try:
        data = await fetch_tools.fetch_json_async(decksite_url('/api/person/{0}'.format(person)))
    except (FetchException, json.decoder.JSONDecodeError):
        return {}
    return data

def post_discord_webhook(webhook_id: str, webhook_token: str, message: str, name: str = None) -> bool:
    if webhook_id is None or webhook_token is None:
        return False
    url = 'https://discordapp.com/api/webhooks/{id}/{token}'.format(id=webhook_id, token=webhook_token)
    fetch_tools.post(url, json_data={
        'content': message,
        'username': name,
    })
    return True

# pylint: disable=unsubscriptable-object
def resources() -> Dict[str, Dict[str, str]]:
    with open('decksite/resources.json') as resources_file:
        return json.load(resources_file, object_pairs_hook=OrderedDict)

async def scryfall_last_updated_async() -> datetime.datetime:
    d = await fetch_tools.fetch_json_async('https://api.scryfall.com/bulk-data')
    for o in d['data']:
        if o['type'] == 'default_cards':
            return dtutil.parse_rfc3339(o['updated_at'])
    raise InvalidDataException(f'Could not get the last updated date from Scryfall: {d}')

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
                    return False, []
                print('Error fetching scryfall data:\n', result_json)
                return False, []
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

    def get_frontside(scr_card: Dict) -> str:
        """If card is transform, returns first name. Otherwise, returns name.
        This is to make sure cards are later found in the database"""
        # not sure how to handle meld cards
        if scr_card['layout'] in ['transform', 'flip', 'adventure', 'modal_dfc']:
            return scr_card['card_faces'][0]['name']
        return scr_card['name']
    result_cardnames = [get_frontside(obj) for obj in result_data]
    return total_cards, result_cardnames

def rulings(cardname: str) -> List[Dict[str, str]]:
    card = fetch_tools.fetch_json('https://api.scryfall.com/cards/named?exact={name}'.format(name=cardname))
    return fetch_tools.fetch_json(card['uri'] + '/rulings')['data']

def sitemap() -> List[str]:
    return fetch_tools.fetch_json(decksite_url('/api/sitemap/'))['urls']

def subreddit() -> Container:
    url = 'https://www.reddit.com/r/pennydreadfulMTG/.rss'
    return feedparser.parse(url)

def time(q: str, twentyfour: bool) -> Dict[str, List[str]]:
    return times_from_timezone_code(q, twentyfour) if len(q) <= 4 else times_from_location(q, twentyfour)

def times_from_timezone_code(q: str, twentyfour: bool) -> Dict[str, List[str]]:
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
    url = 'https://maps.googleapis.com/maps/api/geocode/json?address={q}&key={api_key}&sensor=false'.format(q=fetch_tools.escape(q), api_key=api_key)
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


WISDateType = TypedDict('WISDateType', {
    'exact': str,
    'rough': str,
})

WISSetInfoType = TypedDict('WISSetInfoType', {
    'name': str,
    'code': str,
    'codename': str,
    'mtgoCode': str,
    'symbol': str,
    'enterDate': WISDateType,
    'exitDate': WISDateType,
})

WISSchemaType = TypedDict('WISSchemaType', {
    'deprecated': bool,
    'sets': List[WISSetInfoType],
})

def whatsinstandard() -> WISSchemaType:
    cached = redis.get_container('magic:fetcher:whatisinstandard_6')
    if cached is not None:
        return cached

    # try:
    #     info = fetch_tools.fetch_json('http://whatsinstandard.com/api/v6/standard.json')
    # except FetchException:
    #     cached = redis.get_container('magic:fetcher:whatisinstandard_noex')
    #     if cached is not None:
    #         return cached
    #     raise
    info = json.loads('''{
  "deprecated": false,
  "sets": [
    {
      "name": "Kaladesh",
      "codename": "Lock",
      "code": "KLD",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=KLD",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=KLD",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=KLD",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=KLD"
      },
      "enterDate": {
        "exact": "2016-09-30T00:00:00.000",
        "rough": "September 2016"
      },
      "exitDate": {
        "exact": "2018-10-05T00:00:00.000",
        "rough": "Q4 2018"
      }
    },
    {
      "name": "Aether Revolt",
      "codename": "Stock",
      "code": "AER",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=AER",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=AER",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=AER",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=AER"
      },
      "enterDate": {
        "exact": "2017-01-20T00:00:00.000",
        "rough": "January 2017"
      },
      "exitDate": {
        "exact": "2018-10-05T00:00:00.000",
        "rough": "Q4 2018"
      }
    },
    {
      "name": "Amonkhet",
      "codename": "Barrel",
      "code": "AKH",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=AKH",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=AKH",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=AKH",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=AKH"
      },
      "enterDate": {
        "exact": "2017-04-28T00:00:00.000",
        "rough": "April 2017"
      },
      "exitDate": {
        "exact": "2018-10-05T00:00:00.000",
        "rough": "Q4 2018"
      }
    },
    {
      "name": "Welcome Deck 2017",
      "codename": null,
      "code": "W17",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=W17",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=W17",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=W17",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=W17"
      },
      "enterDate": {
        "exact": "2017-04-28T00:00:00.000",
        "rough": "April 2017"
      },
      "exitDate": {
        "exact": "2018-10-05T00:00:00.000",
        "rough": "Q4 2018"
      }
    },
    {
      "name": "Hour of Devastation",
      "codename": "Laughs",
      "code": "HOU",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=HOU",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=HOU",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=HOU",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=HOU"
      },
      "enterDate": {
        "exact": "2017-07-14T00:00:00.000",
        "rough": "July 2017"
      },
      "exitDate": {
        "exact": "2018-10-05T00:00:00.000",
        "rough": "Q4 2018"
      }
    },
    {
      "name": "Ixalan",
      "codename": "Ham",
      "code": "XLN",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=XLN",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=XLN",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=XLN",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=XLN"
      },
      "enterDate": {
        "exact": "2017-09-29T00:00:00.000",
        "rough": "September 2017"
      },
      "exitDate": {
        "exact": "2019-10-04T00:00:00.000",
        "rough": "Q4 2019"
      }
    },
    {
      "name": "Rivals of Ixalan",
      "codename": "Eggs",
      "code": "RIX",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=RIX",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=RIX",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=RIX",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=RIX"
      },
      "enterDate": {
        "exact": "2018-01-19T00:00:00.000",
        "rough": "January 2018"
      },
      "exitDate": {
        "exact": "2019-10-04T00:00:00.000",
        "rough": "Q4 2019"
      }
    },
    {
      "name": "Dominaria",
      "codename": "Soup",
      "code": "DOM",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=DOM",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=DOM",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=DOM",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=DOM"
      },
      "enterDate": {
        "exact": "2018-04-27T00:00:00.000",
        "rough": "April 2018"
      },
      "exitDate": {
        "exact": "2019-10-04T00:00:00.000",
        "rough": "Q4 2019"
      }
    },
    {
      "name": "Core Set 2019",
      "codename": "Salad",
      "code": "M19",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=M19",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=M19",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=M19",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=M19"
      },
      "enterDate": {
        "exact": "2018-07-13T00:00:00.000",
        "rough": "July 2018"
      },
      "exitDate": {
        "exact": "2019-10-04T00:00:00.000",
        "rough": "Q4 2019"
      }
    },
    {
      "name": "Guilds of Ravnica",
      "codename": "Spaghetti",
      "code": "GRN",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=GRN",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=GRN",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=GRN",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=GRN"
      },
      "enterDate": {
        "exact": "2018-10-05T00:00:00.000",
        "rough": "October 2018"
      },
      "exitDate": {
        "exact": "2020-09-25T00:00:00.000",
        "rough": "Q4 2020"
      }
    },
    {
      "name": "Ravnica Allegiance",
      "codename": "Meatballs",
      "code": "RNA",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=RNA",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=RNA",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=RNA",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=RNA"
      },
      "enterDate": {
        "exact": "2019-01-25T00:00:00.000",
        "rough": "January 2019"
      },
      "exitDate": {
        "exact": "2020-09-25T00:00:00.000",
        "rough": "Q4 2020"
      }
    },
    {
      "name": "War of the Spark",
      "codename": "Milk",
      "code": "WAR",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=WAR",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=WAR",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=WAR",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=WAR"
      },
      "enterDate": {
        "exact": "2019-05-03T00:00:00.000",
        "rough": "May 2019"
      },
      "exitDate": {
        "exact": "2020-09-25T00:00:00.000",
        "rough": "Q4 2020"
      }
    },
    {
      "name": "Core Set 2020",
      "codename": null,
      "code": "M20",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=M20",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=M20",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=M20",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=M20"
      },
      "enterDate": {
        "exact": "2019-07-12T00:00:00.000",
        "rough": "July 2019"
      },
      "exitDate": {
        "exact": "2020-09-25T00:00:00.000",
        "rough": "Q4 2020"
      }
    },
    {
      "name": "Throne of Eldraine",
      "codename": "Archery",
      "code": "ELD",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=ELD",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=ELD",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=ELD",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=ELD"
      },
      "enterDate": {
        "exact": "2019-10-04T00:00:00.000",
        "rough": "October 2019"
      },
      "exitDate": {
        "exact": "2021-09-17T00:00:00.000",
        "rough": "Q3 2021"
      }
    },
    {
      "name": "Theros: Beyond Death",
      "codename": "Baseball",
      "code": "THB",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=THB",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=THB",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=THB",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=THB"
      },
      "enterDate": {
        "exact": "2020-01-24T00:00:00.000",
        "rough": "January 2020"
      },
      "exitDate": {
        "exact": "2021-09-17T00:00:00.000",
        "rough": "Q3 2021"
      }
    },
    {
      "name": "Ikoria: Lair of Behemoths",
      "codename": "Cricket",
      "code": "IKO",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=IKO",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=IKO",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=IKO",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=IKO"
      },
      "enterDate": {
        "exact": "2020-04-24T00:00:00.000",
        "rough": "April 2020"
      },
      "exitDate": {
        "exact": "2021-09-17T00:00:00.000",
        "rough": "Q3 2021"
      }
    },
    {
      "name": "Core Set 2021",
      "codename": null,
      "code": "M21",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=M21",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=M21",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=M21",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=M21"
      },
      "enterDate": {
        "exact": "2020-07-03T00:00:00.000",
        "rough": "Q3 2020"
      },
      "exitDate": {
        "exact": "2021-09-17T00:00:00.000",
        "rough": "Q3 2021"
      }
    },
    {
      "name": "Zendikar Rising",
      "codename": "Diving",
      "code": "ZNR",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=ZNR",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=ZNR",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=ZNR",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=ZNR"
      },
      "enterDate": {
        "exact": "2020-09-25T00:00:00.000",
        "rough": "Q4 2020"
      },
      "exitDate": {
        "exact": null,
        "rough": "Q4 2022"
      }
    },
    {
      "name": "Kaldheim",
      "codename": "Equestrian",
      "code": "KHM",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=KHM",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=KHM",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=KHM",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=KHM"
      },
      "enterDate": {
        "exact": "2021-02-05T00:00:00.000",
        "rough": "Q1 2021"
      },
      "exitDate": {
        "exact": null,
        "rough": "Q4 2022"
      }
    },
    {
      "name": "Strixhaven: School of Mages",
      "codename": "Fencing",
      "code": "STX",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=STX",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=STX",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=STX",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=STX"
      },
      "enterDate": {
        "exact": "2021-04-23T00:00:00.000",
        "rough": "Q2 2021"
      },
      "exitDate": {
        "exact": null,
        "rough": "Q4 2022"
      }
    },
    {
      "name": "Dungeons & Dragons: Adventures in the Forgotten Realms",
      "codename": null,
      "code": "AFR",
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=AFR",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=AFR",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=AFR",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=AFR"
      },
      "enterDate": {
        "exact": "2021-07-16T00:00:00.000",
        "rough": "Q3 2021"
      },
      "exitDate": {
        "exact": null,
        "rough": "Q4 2022"
      }
    },
    {
      "name": "Innistrad: Midnight Hunt",
      "codename": "Golf",
      "code": null,
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=null",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=null",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=null",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=null"
      },
      "enterDate": {
        "exact": "2021-09-17T00:00:00.000",
        "rough": "Q3 2021"
      },
      "exitDate": {
        "exact": null,
        "rough": "Q4 2023"
      }
    },
    {
      "name": "Innistrad: Crimson Vow",
      "codename": "Golf",
      "code": null,
      "symbol": {
        "common": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=C&set=null",
        "uncommon": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=U&set=null",
        "rare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=R&set=null",
        "mythicRare": "http://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&size=large&rarity=M&set=null"
      },
      "enterDate": {
        "exact": "2021-11-19T00:00:00.000",
        "rough": "Q4 2021"
      },
      "exitDate": {
        "exact": null,
        "rough": "Q4 2023"
      }
    }
  ],
  "bans": [
    {
      "cardName": "Oko, Thief of Crowns",
      "cardImageUrl": "https://img.scryfall.com/cards/png/front/3/4/3462a3d0-5552-49fa-9eb7-100960c55891.png",
      "setCode": "ELD",
      "reason": "Banned for its power level being higher than is healthy for current and future Standard metagame environments.",
      "announcementUrl": "https://magic.wizards.com/en/articles/archive/news/november-18-2019-banned-and-restricted-announcement"
    },
    {
      "cardName": "Once Upon a Time",
      "cardImageUrl": "https://img.scryfall.com/cards/png/front/4/0/4034e5ba-9974-43e3-bde7-8d9b4586c3a4.png",
      "setCode": "ELD",
      "reason": "Banned for contributing to a high consistency of strong starts for green, providing a level of early mana fixing that other colors don't have access to.",
      "announcementUrl": "https://magic.wizards.com/en/articles/archive/news/november-18-2019-banned-and-restricted-announcement"
    },
    {
      "cardName": "Fires of Invention",
      "cardImageUrl": "https://img.scryfall.com/cards/png/front/a/1/a12b16b0-f75f-42d8-9b24-947c1908e0f7.png",
      "setCode": "ELD",
      "reason": "Banned for introducing too many risks and design constraints to the future of Standard.",
      "announcementUrl": "https://magic.wizards.com/en/articles/archive/news/june-1-2020-banned-and-restricted-announcement"
    },
    {
      "cardName": "Cauldron Familiar",
      "cardImageUrl": "https://img.scryfall.com/cards/png/front/9/a/9a539a23-8383-4525-82dd-acfe1d219fe9.png",
      "setCode": "ELD",
      "reason": "Banned for reducing metagame diversity and for being cumbersome to play against.",
      "announcementUrl": "https://magic.wizards.com/en/articles/archive/news/august-8-2020-banned-and-restricted-announcement"
    },
    {
      "cardName": "Uro, Titan of Nature's Wrath",
      "cardImageUrl": "https://c1.scryfall.com/file/scryfall-cards/png/front/a/0/a0b6a71e-56cb-4d25-8f2b-7a4f1b60900d.png",
      "setCode": "THB",
      "reason": "Banned for weakening four-colour ramp decks.",
      "announcementUrl": "https://magic.wizards.com/en/articles/archive/news/september-28-2020-banned-and-restricted-announcement-2020-09-28"
    },
    {
      "cardName": "Omnath, Locus of Creation",
      "cardImageUrl": "https://c1.scryfall.com/file/scryfall-cards/large/front/4/e/4e4fb50c-a81f-44d3-93c5-fa9a0b37f617.jpg?1602499748",
      "setCode": "ZNR",
      "reason": "Banned for being too strong in four-color ramp decks.",
      "announcementUrl": "https://magic.wizards.com/en/articles/archive/news/october-12-2020-banned-and-restricted-announcement?adf"
    },
    {
      "cardName": "Lucky Clover",
      "cardImageUrl": "https://c1.scryfall.com/file/scryfall-cards/large/front/4/b/4b5d23a6-3a23-4169-aea1-f10bf5153180.jpg?1602499760",
      "setCode": "ELD",
      "reason": "Banned for being a powerful and difficult-to-interact-with part of Adventure decks.",
      "announcementUrl": "https://magic.wizards.com/en/articles/archive/news/october-12-2020-banned-and-restricted-announcement?adf"
    },
    {
      "cardName": "Escape to the Wilds",
      "cardImageUrl": "https://c1.scryfall.com/file/scryfall-cards/large/front/3/e/3e26c10b-179f-4a6e-bc8d-3ec1d6783fb9.jpg?1602499769",
      "setCode": "ELD",
      "reason": "Banned for being a unique and powerful bridge between strong ramp enablers and powerful payoffs.",
      "announcementUrl": "https://magic.wizards.com/en/articles/archive/news/october-12-2020-banned-and-restricted-announcement?adf"
    }
  ]
}''')
    redis.store('magic:fetcher:whatisinstandard_6', info, ex=86400)
    redis.store('magic:fetcher:whatisinstandard_noex', info)
    return info
