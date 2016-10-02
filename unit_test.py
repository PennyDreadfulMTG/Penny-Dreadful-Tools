import calendar
import os
import time
from email.utils import formatdate

import card
import command
import configuration
import fetcher
import oracle


# Check that we can fetch card images.
def test_imagedownload():
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='island.jpg')
    if command.acceptable_file(filepath):
        os.remove(filepath)
    c = card.Card({'name': 'Island'})
    assert command.download_image([c]) is not None

# Check that we can fall back to the Gatherer images if all else fails.
def test_fallbackimagedownload():
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='avon_island.jpg')
    if command.acceptable_file(filepath):
        os.remove(filepath)
    c = card.Card({'name': 'Avon Island', 'multiverse_id': 26301})
    assert command.download_image([c]) is not None

# Check that we can succesfully fail at getting an image
def test_noimageavailable():
    c = card.Card({'name': "Barry's Land", 'multiverse_id': 0})
    assert command.download_image([c]) is None

# Search for a single card via full name
def test_solo_query():
    names = command.parse_queries('[Gilder Bairn]')
    assert len(names) == 1
    assert names[0] == 'gilder bairn'
    cards = command.cards_from_queries(names, oracle.Oracle())
    assert len(cards) == 1

# Two cards, via full name
def test_double_query():
    names = command.parse_queries('[Mother of Runes] [Ghostfire]')
    assert len(names) == 2
    cards = command.cards_from_queries(names, oracle.Oracle())
    assert len(cards) == 2

# The following two sets assume that Kamahl is a long dead character, and is getting no new cards.
# If wizards does an Onslaught/Odyssey throwback in some supplimental product, they may start failing.
def test_legend_query():
    names = command.parse_queries('[Kamahl]')
    assert len(names) == 1
    cards = command.cards_from_queries(names, oracle.Oracle())
    assert len(cards) == 2

def test_partial_query():
    names = command.parse_queries("[Kamahl's]")
    assert len(names) == 1
    cards = command.cards_from_queries(names, oracle.Oracle())
    assert len(cards) == 3

# Check that the list of legal cards is being fetched correctly.
# BAKERT this test now very problematic
# def test_legality_list():
#     command.update_legality()
#     assert len(command.STATE.legal_cards) > 0

def test_legality_emoji():
    legal_cards = fetcher.legal_cards()
    legal_card = command.cards_from_query('island', oracle.Oracle())[0]
    assert command.legal_emoji(legal_card, legal_cards) == ':white_check_mark:'
    illegal_card = command.cards_from_query('black lotus', oracle.Oracle())[0]
    assert command.legal_emoji(illegal_card, legal_cards) == ':no_entry_sign:'
    assert command.legal_emoji(illegal_card, legal_cards, True) == ':no_entry_sign: (not legal in PD)'

def test_accents():
    cards = command.cards_from_query('Lim-Dûl the Necromancer', oracle.Oracle())
    assert len(cards) == 1
    cards = command.cards_from_query('Séance', oracle.Oracle())
    assert len(cards) == 1

    # The following two don't currently work. But should be turned on once they do.

    #cards = command.cards_from_query('Lim-Dul the Necromancer')
    #assert len(cards) == 1
    #cards = command.cards_from_query('Seance')
    #assert len(cards) == 1

def test_aether():
    cards = command.cards_from_query('Æther Spellbomb', oracle.Oracle())
    assert len(cards) == 1
    #cards = command.cards_from_query('aether Spellbomb')
    #assert len(cards) == 1


def test_fetcher_mod_since():
    lmtime = calendar.timegm(time.gmtime()) - 10
    lmtime = formatdate(timeval=lmtime, localtime=False, usegmt=True)
    val = fetcher.fetch("http://pdmtgo.com/legal_cards.txt", if_modified_since=lmtime)
    assert val == ''
