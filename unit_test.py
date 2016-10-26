import os

import command

from magic import card, configuration, fetcher, oracle, fetcher_internal

# Check that we can fetch card images.
def test_imagedownload():
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='island.jpg')
    if command.acceptable_file(filepath):
        os.remove(filepath)
    c = card.Card({'id': 0, 'name': 'Island', 'names': 'Island'})
    assert command.download_image([c]) is not None

# Check that we can fall back to the Gatherer images if all else fails.
# Note: bluebones doesn't have Nalathni Dragon, while Gatherer does, which makes it slightly unique
def test_fallbackimagedownload():
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='nalathni-dragon.jpg')
    if command.acceptable_file(filepath):
        os.remove(filepath)
    c = []
    c.extend(command.cards_from_query('Nalathni Dragon'))
    assert command.download_image(c) is not None

# Check that we can succesfully fail at getting an image
def test_noimageavailable():
    c = card.Card({'name': "Barry's Land", 'id': 0, 'multiverseid': 0, 'names': "Barry's Land"})
    assert command.download_image([c]) is None

# Search for a single card via full name
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
    legal_cards = oracle.get_legal_cards(True)
    assert len(legal_cards) > 0

def test_legality_emoji():
    legal_cards = oracle.get_legal_cards()
    assert len(legal_cards) > 0
    legal_card = command.cards_from_query('island')[0]
    assert command.legal_emoji(legal_card, legal_cards) == ':white_check_mark:'
    illegal_card = command.cards_from_query('black lotus')[0]
    assert command.legal_emoji(illegal_card, legal_cards) == ':no_entry_sign:'
    assert command.legal_emoji(illegal_card, legal_cards, True) == ':no_entry_sign: (not legal in PD)'

def test_accents():
    cards = command.cards_from_query('Lim-Dûl the Necromancer')
    assert len(cards) == 1
    cards = command.cards_from_query('Séance')
    assert len(cards) == 1
    cards = command.cards_from_query('Lim-Dul the Necromancer')
    assert len(cards) == 1
    cards = command.cards_from_query('Seance')
    assert len(cards) == 1

def test_aether():
    #cards = command.cards_from_query('Æther Spellbomb')
    #assert len(cards) == 1
    cards = command.cards_from_query('aether Spellbomb')
    assert len(cards) == 1


def test_fetcher_mod_since():
    resource_id = 'test_fetcher_mod_since'
    fetcher_internal.remove_last_modified(resource_id)
    fetcher.fetch("http://pdmtgo.com/legal_cards.txt", resource_id=resource_id)
    assert fetcher_internal.get_last_modified(resource_id) is not None
    assert fetcher_internal.get_cached_text(resource_id) is not None

def test_split_cards():
    cards = command.cards_from_query('Armed // Dangerous')
    assert len(cards) == 1

    assert command.download_image(cards) != None

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
    cards = oracle.search('Cancle')
    assert('Cancel' in [c.name for c in cards])
    cards = oracle.search('Knight of the White Rohcid')
    assert('Knight of the White Orchid' in [c.name for c in cards])
