import inspect
import json
import os
import random
import string

DEFAULTS = {
    'card_alias_file': './card_aliases.tsv',
    'charts_dir': './images/charts',
    'decksite_database': 'decksite',
    'decksite_hostname': 'pennydreadfulmagic.com',
    'decksite_port': 80,
    'decksite_protocol': 'https',
    'github_password': None,
    'github_user': None,
    'guild_id': '',
    'image_dir': './images',
    'legality_dir': '~/legality/Legality Checker/',
    'magic_database': 'cards',
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
    'web_cache': '.web_cache'
}

def get(key):
    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}
    if key in cfg:
        return cfg[key]
    elif key in os.environ:
        cfg[key] = os.environ[key]
    else:
        # Lock in the default value if we use it.
        cfg[key] = DEFAULTS[key]

        if inspect.isfunction(cfg[key]): # If default value is a function, call it.
            cfg[key] = cfg[key]()

    print("CONFIG: {0}={1}".format(key, cfg[key]))
    fh = open('config.json', 'w')
    fh.write(json.dumps(cfg, indent=4))
    return cfg[key]

def write(key, value):
    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}

    cfg[key] = value

    print("CONFIG: {0}={1}".format(key, cfg[key]))
    fh = open('config.json', 'w')
    fh.write(json.dumps(cfg, indent=4))
    return cfg[key]
