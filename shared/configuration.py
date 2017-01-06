import json
import os

DEFAULTS = {
    'card_alias_file': './card_aliases.tsv',
    'database': './cards.sqlite',
    'decksite_database': './decksite',
    'image_dir': './images',
    'magic_database': './cards.sqlite',
    'prices_database': './prices.db',
    'pricesdb': './prices.db',
    'scratch_dir': '.',
    'spellfix': './spellfix',
    'to_password': '',
    'to_username': '',
    'github_user': '',
    'github_password': '',
    'mysql_host': 'localhost',
    'mysql_port': 3306,
    'mysql_user': 'pennydreadful',
    'mysql_passwd': '',
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
        fh = open('config.json', 'w')
        fh.write(json.dumps(cfg, indent=4))
        return cfg[key]
    else:
        # Lock in the default value if we use it.
        cfg[key] = DEFAULTS[key]
        fh = open('config.json', 'w')
        fh.write(json.dumps(cfg, indent=4))
    return DEFAULTS[key]
