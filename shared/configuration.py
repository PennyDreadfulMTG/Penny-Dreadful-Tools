import json

DEFAULTS = {
    'card_alias_file': './card_aliases.tsv',
    'database': './cards.sqlite',
    'decksite_database': './decksite.sqlite',
    'image_dir': './images',
    'magic_database': './cards.sqlite',
    'prices_database': './prices.db',
    'pricesdb': './prices.db',
    'scratch_dir': '.',
    'spellfix': './spellfix',
    'to_password': '',
    'to_username': '',
    'github_user': '',
    'github_password': ''
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
