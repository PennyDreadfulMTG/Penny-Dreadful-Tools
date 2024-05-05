import inspect
import json
import os
import random
import re
import string
from typing import Any, overload

from shared.pd_exception import InvalidArgumentException
from shared.settings import CONFIG, BoolSetting, IntSetting, ListSetting, StrSetting, fail, save_cfg

try:
    import dotenv
    dotenv.load_dotenv('.')
except ImportError:
    print("Couldn't load .env")

RE_SUBKEY = re.compile(r'(\w+)\.(\w+)')

# === Decksite ===
# On production, /rotation/ turns off when not active.
always_show_rotation = BoolSetting('always_show_rotation', False)
is_test_site = BoolSetting('is_test_site', False)

# === Discord Bot ===
# Which format should checkmarks represent?
legality_format = StrSetting('legality_format', 'Penny Dreadful', configurable=True, doc='Which format should the bot mark legality for?')
dismiss_any = BoolSetting('dismiss_any', True, configurable=True, doc='Allows ❎ to dismiss any message')
# Should !time use the 24-hour format?
use_24h = BoolSetting('use_24h', False, configurable=True, doc='Use a 24 hour clock')
# Google Custom Search Engine (for !google)
cse_api_key = StrSetting('cse_api_key', '')
cse_engine_id = StrSetting('cse_engine_id', '')
bot_debug = BoolSetting('bot_debug', False)
token = StrSetting('token', '')
pd_server_id = IntSetting('pd_server_id', 207281932214599682)

# === Magic ===
# Path to TSV list of card nicknames.  Should never be changed.  Used by magic.
card_alias_file = StrSetting('card_alias_file', './card_aliases.tsv')
# Path to list of is:spikey cards.
is_spikey_file = StrSetting('is_spikey_file', './.is-spikey.txt')
# Block Scryfall updates when things are broken
prevent_cards_db_updates = BoolSetting('prevent_cards_db_updates', False)

last_good_bulk_data = StrSetting('last_good_bulk_data', '')


# === Prices & Rotation ===
# Array of Pricefile URLs (foil, non-foil).  Used by price_grabber and rotation_script
cardhoarder_urls: ListSetting[str] = ListSetting('cardhoarder_urls', [])
# Block some of the more dangerous things from running if this is true
production = BoolSetting('production', False)

# === Modo Bugs ===
# Discord Webhook endpoint
bugs_webhook_id = StrSetting('bugs_webhook_id', '')
bugs_webhook_token = StrSetting('bugs_webhook_token', '')

# === Shared ===
# Is the codebase allowed to report github issues?  Disable on dev.
create_github_issues = BoolSetting('create_github_issues', True)
# == Redis ==
redis_enabled = BoolSetting('redis_enabled', True)
# == Mysql ==
mysql_host = StrSetting('mysql_host', 'localhost')
mysql_port = IntSetting('mysql_port', 3306)
mysql_user = StrSetting('mysql_user', 'pennydreadful')
mysql_passwd = StrSetting('mysql_passwd', '')
# == Discord API ==
oauth2_client_id = StrSetting('oauth2_client_id', '')
oauth2_client_secret = StrSetting('oauth2_client_secret', '')

DEFAULTS: dict[str, Any] = {
    # mysql database name.  Used by decksite.
    'decksite_database': 'decksite',
    # mysql database name.  Used by decksite tests.
    'decksite_test_database': 'decksite_test',
    # URL for decksite API calls.  Used by discordbot.
    'decksite_hostname': 'pennydreadfulmagic.com',
    'decksite_port': 80,
    'decksite_protocol': 'https',
    # github credentials.  Used for auto-reporting issues.
    'github_password': None,
    'github_user': None,
    # Google Maps API key (for !time)
    'google_maps_api_key': None,
    # Required if you want to share cookies between subdomains
    'flask_cookie_domain': None,
    'flask_server_name': None,
    # Discord server id.  Used for admin verification.  Used by decksite.
    'guild_id': '207281932214599682',
    'image_dir': './images',
    # Discord Webhook endpoint
    'league_webhook_id': None,
    'league_webhook_token': None,
    'legality_dir': '~/legality/Legality Checker/',
    'logsite_protocol': 'https',
    'logsite_hostname': 'logs.pennydreadfulmagic.com',
    'logsite_port': 80,
    'logsite_database': 'pdlogs',
    'magic_database': 'cards',
    'modo_bugs_dir': 'modo_bugs_repo',
    'not_pd': '',
    'pdbot_api_token': lambda: ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(32)),
    'poeditor_api_key': None,
    'prices_database': 'prices',
    'redis_db': 0,
    'redis_host': 'localhost',
    'redis_port': 6379,
    # Discord channel id to emit rotation-in-progress messages to.
    'rotation_hype_channel_id': '207281932214599682',
    'scratch_dir': '.',
    'sentry_token': None,
    'sentry_monitorslug_rotation_script': None,
    'slow_fetch': 10.0,
    'slow_page': 10.0,
    'slow_query': 5.0,
    'slow_bot_start': 30,
    'to_password': '',
    'to_username': '',
    'tournament_channel_id': '334220558159970304',
    'tournament_reminders_channel_id': '207281932214599682',
    'typeahead_data_path': 'shared_web/static/dist/typeahead.json',
    'web_cache': '.web_cache',
    'whoosh_index_dir': 'whoosh_index',
    # Dreadrise top-level URL. used for dreadrise-based searches.
    # the first variable is used for requests, the second variable is used for links displayed to user
    'dreadrise_url': 'https://penny.dreadrise.xyz',
    'dreadrise_public_url': 'https://penny.dreadrise.xyz',
    'mos_premodern_channel_id': '921967538907271258',
}

def get_optional_str(key: str) -> str | None:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, str):
        return val
    raise fail(key, val, str)

def get_str(key: str) -> str:
    val = get_optional_str(key)
    if val is None:
        raise fail(key, val, str)
    return val

def get_optional_int(key: str) -> int | None:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        # required so that we can pass int-values in environment variables
        CONFIG[key] = int(val)
        return CONFIG[key]
    raise fail(key, val, int)

def get_int(key: str) -> int:
    val = get_optional_int(key)
    if val is None:
        raise fail(key, val, int)
    return val

def get_float(key: str) -> float | None:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, float):
        return val
    if isinstance(val, int):
        return write(key, float(val))
    if isinstance(val, str):
        # required so that we can pass int-values in environment variables
        CONFIG[key] = float(val)
        return CONFIG[key]

    raise fail(key, val, float)

def get_list(key: str) -> list[str]:
    val = get(key)
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return val.split(',')
    raise fail(key, val, list[str])

def get(key: str) -> str | list[str] | int | float | None:
    if key in CONFIG:
        return CONFIG[key]
    subkey = RE_SUBKEY.match(key)
    if subkey:
        raise NotImplementedError

    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}
    if key in os.environ:
        cfg[key] = os.environ[key]
        print(f'CONFIG: {key}={cfg[key]}')
        return cfg[key]
    if key in cfg:
        CONFIG.update(cfg)
        return cfg[key]
    if key in DEFAULTS:
        # Lock in the default value if we use it.
        cfg[key] = DEFAULTS[key]

        if inspect.isfunction(cfg[key]):  # If default value is a function, call it.
            cfg[key] = cfg[key]()
    else:
        raise InvalidArgumentException(f'No default or other configuration value available for {key}')

    print(f'CONFIG: {key}={cfg[key]}')
    save_cfg(cfg)
    return cfg[key]

@overload
def write(key: str, value: str) -> str:
    pass

@overload
def write(key: str, value: int) -> int:
    pass

@overload
def write(key: str, value: float) -> float:
    pass

@overload
def write(key: str, value: set[str]) -> set[str]:
    pass

def write(key: str, value: str | list[str] | set[str] | int | float) -> str | list[str] | set[str] | int | float:
    subkey = RE_SUBKEY.match(key)
    filename = 'config.json'
    fullkey = key
    if subkey:
        filename = os.path.join('configs', f'{subkey.group(1)}.config.json')
        key = subkey.group(2)

    try:
        cfg = json.load(open(filename))
    except FileNotFoundError:
        cfg = {}

    if isinstance(value, set):
        value = list(value)

    cfg[key] = value
    CONFIG[fullkey] = value

    print(f'CONFIG: {fullkey}={cfg[key]}')
    save_cfg(cfg)
    return cfg[key]

def server_name() -> str:
    return get_str('decksite_hostname') + ':{port}'.format(port=get_int('decksite_port')) if get_optional_int('decksite_port') else ''
