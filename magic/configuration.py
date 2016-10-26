import json

DEFAULTS = {
    'card_alias_file': './card_aliases.tsv',
    'database': './db',
    'decksite_database': './decksite.db',
    'image_dir': '.',
    'pricesdb': './prices.db',
    'spellfix': './spellfix'
}

def get(key):
    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}
    if key in cfg:
        return cfg[key]
    return DEFAULTS[key]
