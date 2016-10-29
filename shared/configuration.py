import json

DEFAULTS = {
    'card_alias_file': './card_aliases.tsv',
    'database': './db',
    'decksite_database': './decksite.db',
    'image_dir': '.',
    'magic_database': './db',
    'prices_database': './prices.db',
    'pricesdb': './prices.db',
    'scratch_dir': '.',
    'spellfix': './spellfix',
    'to_password': '',
    'to_username': ''
}

def get(key):
    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}
    if key in cfg:
        return cfg[key]
    else:
        # Lock in the default value if we use it.
        cfg[key] = DEFAULTS[key]
        fh = open('config.json', 'w')
        fh.write(json.dumps(cfg, indent=4))
    return DEFAULTS[key]
