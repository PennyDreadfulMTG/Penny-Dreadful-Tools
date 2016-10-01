import json

DEFAULTS = {
    'database': './db',
    'image_dir': '.',
    'card_alias_file': './card_aliases.tsv'
}

def get(key):
    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}
    if key in cfg:
        return cfg[key]
    return DEFAULTS[key]
