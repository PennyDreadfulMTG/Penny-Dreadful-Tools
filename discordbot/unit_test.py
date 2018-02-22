import os

from discordbot import command, emoji
from magic import card, fetcher_internal, image_fetcher, oracle
from magic.database import db
from shared import configuration


# Check that we can fetch card images.
def test_imagedownload():
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='island.jpg')
    if fetcher_internal.acceptable_file(filepath):
        os.remove(filepath)
    c = []
    c.extend(oracle.cards_from_query('Island'))
    assert image_fetcher.download_image(c) is not None

# Check that we can fall back to the Gatherer images if all else fails.
# Note: bluebones doesn't have Nalathni Dragon, while Gatherer does, which makes it useful here.
def test_fallbackimagedownload():
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='nalathni-dragon.jpg')
    if fetcher_internal.acceptable_file(filepath):
        os.remove(filepath)
    c = []
    c.extend(oracle.cards_from_query('Nalathni Dragon'))
    assert image_fetcher.download_image(c) is not None

# Check that we can succesfully fail at getting an image.
def test_noimageavailable():
    c = card.Card({'name': "Barry's Land", 'id': 0, 'multiverseid': 0, 'names': "Barry's Land"})
    assert image_fetcher.download_image([c]) is None

# Search for a single card via full name,
def test_solo_query():
    names = command.parse_queries('[Gilder Bairn]')
    assert len(names) == 1
    assert names[0] == 'gilder bairn'
    cards = command.cards_from_queries(names)
    assert len(cards) == 1

# Two cards, via full name
def test_double_query():
    names = command.parse_queries('[Mother of Runes] [Ghostfire]')
    assert len(names) == 2
    cards = command.cards_from_queries(names)
    assert len(cards) == 2

# The following two sets assume that Kamahl is a long dead character, and is getting no new cards.
# If wizards does an Onslaught/Odyssey throwback in some supplimental product, they may start failing.
def test_legend_query():
    names = command.parse_queries('[Kamahl]')
    assert len(names) == 1
    cards = command.cards_from_queries(names)
    assert len(cards) == 2

def test_partial_query():
    names = command.parse_queries("[Kamahl's]")
    assert len(names) == 1
    cards = command.cards_from_queries(names)
    assert len(cards) == 3

# Check that the list of legal cards is being fetched correctly.
def test_legality_list():
    legal_cards = oracle.legal_cards()
    assert len(legal_cards) > 0

def test_legality_emoji():
    legal_cards = oracle.legal_cards()
    assert len(legal_cards) > 0
    legal_card = oracle.cards_from_query('island')[0]
    assert emoji.legal_emoji(legal_card) == ':white_check_mark:'
    illegal_card = oracle.cards_from_query('black lotus')[0]
    assert emoji.legal_emoji(illegal_card) == ':no_entry_sign:'
    assert emoji.legal_emoji(illegal_card, True) == ':no_entry_sign: (not legal in PD)'

def test_accents():
    cards = oracle.cards_from_query('Lim-Dûl the Necromancer')
    assert len(cards) == 1
    cards = oracle.cards_from_query('Séance')
    assert len(cards) == 1
    cards = oracle.cards_from_query('Lim-Dul the Necromancer')
    assert len(cards) == 1
    cards = oracle.cards_from_query('Seance')
    assert len(cards) == 1

def test_aether():
    cards = oracle.cards_from_query('aether Spellbomb')
    assert len(cards) == 1

def test_split_cards():
    cards = oracle.cards_from_query('Armed // Dangerous')
    assert len(cards) == 1
    assert image_fetcher.download_image(cards) is not None
    names = command.parse_queries('[Toil // Trouble]')
    assert len(names) == 1
    cards = command.cards_from_queries(names)
    assert len(cards) == 1

def test_some_names():
    cards = oracle.search(' of the Reliquary')
    assert('Knight of the Reliquary' in [c.name for c in cards])
    cards = oracle.search('Séance')
    assert('Séance' in [c.name for c in cards])
    cards = oracle.search('Seance')
    assert('Séance' in [c.name for c in cards])
    cards = oracle.search('sean')
    assert('Séance' in [c.name for c in cards])
    cards = oracle.search('Jötun Grunt')
    assert('Jötun Grunt' in [c.name for c in cards])
    cards = oracle.search('Jotun Grunt')
    assert('Jötun Grunt' in [c.name for c in cards])
    cards = oracle.search('Chittering Host')
    assert('Graf Rats' in [c.name for c in cards])
    assert('Midnight Scavengers' in [c.name for c in cards])
    cards = oracle.search('Wastes')
    assert('Wastes' in [c.name for c in cards])
    # We don't support fuzzy matching on MySQL, yet.
    if db().is_sqlite():
        cards = oracle.search('Cancle')
        assert('Cancel' in [c.name for c in cards])
        cards = oracle.search('Knight of the White Rohcid')
        assert('Knight of the White Orchid' in [c.name for c in cards])
