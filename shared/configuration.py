import inspect
import json
import os
import random
import string
from typing import List, Union

from shared.pd_exception import InvalidArgumentException, InvalidDataException

DEFAULTS = {
    'cardhoarder_urls': [],
    'card_alias_file': './card_aliases.tsv',
    'charts_dir': './images/charts',
    'decksite_database': 'decksite',
    'decksite_hostname': 'pennydreadfulmagic.com',
    'decksite_port': 80,
    'decksite_protocol': 'https',
    'github_password': None,
    'github_user': None,
    'guild_id': '207281932214599682',
    'image_dir': './images',
    'legality_dir': '~/legality/Legality Checker/',
    'magic_database': 'cards',
    'mtgotraders_url': None,
    'mysql_host': 'localhost',
    'mysql_passwd': '',
    'mysql_port': 3306,
    'mysql_user': 'pennydreadful',
    'not_pd': '',
    'oauth2_client_id': '',
    'oauth2_client_secret': '',
    'otherbot_commands': '!s,!card,!ipg,!mtr,!cr,!define',
    'pdbot_api_token': lambda: ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(32)),
    'prices_database': 'prices',
    'scratch_dir': '.',
    'slow_fetch': 10,
    'slow_page': 10,
    'slow_query': 5,
    'spellfix': './spellfix',
    'to_password': '',
    'to_username': '',
    'tournament_channel_id': '207281932214599682',
    'web_cache': '.web_cache',
    'cse_api_key': None,
    'cse_engine_id': None,
    'whoosh_index_dir': 'whoosh_index',
    'poeditor_api_key': None,
    'league_webhook_id': None,
    'league_webhook_token': None,
}

def get_str(key: str) -> str:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, str):
        return val
    fail(key, val, str)

def get_int(key: str) -> int:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, int):
        return val
    fail(key, val, int)

def get_float(key: str) -> float:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, float):
        return val
    fail(key, val, int)

def get_list(key: str) -> List[str]:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, list):
        return val
    fail(key, val, List[str])

def get(key: str) -> Union[str, List[str], int]:
    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}
    if key in cfg:
        return cfg[key]
    elif key in os.environ:
        cfg[key] = os.environ[key]
    elif key in DEFAULTS:
        # Lock in the default value if we use it.
        cfg[key] = DEFAULTS[key]

        if inspect.isfunction(cfg[key]): # If default value is a function, call it.
            cfg[key] = cfg[key]()
    else:
        raise InvalidArgumentException('No default or other configuration value available for {key}'.format(key=key))

    print("CONFIG: {0}={1}".format(key, cfg[key]))
    fh = open('config.json', 'w')
    fh.write(json.dumps(cfg, indent=4))
    return cfg[key]

def write(key: str, value: str) -> str:
    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}

    cfg[key] = value

    print("CONFIG: {0}={1}".format(key, cfg[key]))
    fh = open('config.json', 'w')
    fh.write(json.dumps(cfg, indent=4, sort_keys=True))
    return cfg[key]

def fail(key, val, expected_type):
    raise InvalidDataException('Expected a {expected_type} for {key}, got `{val}` ({actual_type})'.format(expected_type=expected_type, key=key, val=val, actual_type=type(val)))
