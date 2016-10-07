import calendar
import os
import time
from email.utils import formatdate

import card
import command
import configuration
import fetcher
import oracle

ORACLE = oracle.Oracle()
# Check that we can fetch card images.
def test_imagedownload():
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='island.jpg')
    if command.acceptable_file(filepath):
        os.remove(filepath)
    c = card.Card({'name': 'Island'})
    assert command.download_image([c], ORACLE) is not None

# Check that we can fall back to the Gatherer images if all else fails.
# Note: Bluebones doesn't have Nalathni Dragon, while Gatherer does, which makes it slightly unique
def test_fallbackimagedownload():
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='nalathni-dragon.jpg')
    if command.acceptable_file(filepath):
        os.remove(filepath)
    c = []
    c.extend(command.cards_from_query('Nalathni Dragon', ORACLE))
    assert command.download_image(c, ORACLE) is not None

# Check that we can succesfully fail at getting an image
def test_noimageavailable():
    c = card.Card({'name': "Barry's Land", 'id': 0, 'multiverseid': 0})
    assert command.download_image([c], ORACLE) is None

# Search for a single card via full name
def test_solo_query():
    names = command.parse_queries('[Gilder Bairn]')
    assert len(names) == 1
    assert names[0] == 'gilder bairn'
    cards = command.cards_from_queries(names, ORACLE)
    assert len(cards) == 1

# Two cards, via full name
def test_double_query():
    names = command.parse_queries('[Mother of Runes] [Ghostfire]')
    assert len(names) == 2
    cards = command.cards_from_queries(names, ORACLE)
    assert len(cards) == 2

# The following two sets assume that Kamahl is a long dead character, and is getting no new cards.
# If wizards does an Onslaught/Odyssey throwback in some supplimental product, they may start failing.
def test_legend_query():
    names = command.parse_queries('[Kamahl]')
    assert len(names) == 1
    cards = command.cards_from_queries(names, ORACLE)
    assert len(cards) == 2

def test_partial_query():
    names = command.parse_queries("[Kamahl's]")
    assert len(names) == 1
    cards = command.cards_from_queries(names, ORACLE)
    assert len(cards) == 3

# Check that the list of legal cards is being fetched correctly.
def test_legality_list():
    legal_cards = ORACLE.get_legal_cards()
    assert len(legal_cards) > 0

def test_legality_emoji():
    legal_cards = ORACLE.get_legal_cards()
    assert len(legal_cards) > 0
    legal_card = command.cards_from_query('island', ORACLE)[0]
    assert command.legal_emoji(legal_card, legal_cards) == ':white_check_mark:'
    illegal_card = command.cards_from_query('black lotus', ORACLE)[0]
    assert command.legal_emoji(illegal_card, legal_cards) == ':no_entry_sign:'
    assert command.legal_emoji(illegal_card, legal_cards, True) == ':no_entry_sign: (not legal in PD)'

def test_accents():
    cards = command.cards_from_query('Lim-Dûl the Necromancer', ORACLE)
    assert len(cards) == 1
    cards = command.cards_from_query('Séance', ORACLE)
    assert len(cards) == 1
    cards = command.cards_from_query('Lim-Dul the Necromancer', ORACLE)
    assert len(cards) == 1
    cards = command.cards_from_query('Seance', ORACLE)
    assert len(cards) == 1

def test_aether():
    cards = command.cards_from_query('Æther Spellbomb', ORACLE)
    assert len(cards) == 1
    #cards = command.cards_from_query('aether Spellbomb')
    #assert len(cards) == 1


def test_fetcher_mod_since():
    lmtime = calendar.timegm(time.gmtime()) - 10
    lmtime = formatdate(timeval=lmtime, localtime=False, usegmt=True)
    val = fetcher.fetch("http://pdmtgo.com/legal_cards.txt", if_modified_since=lmtime)
    assert val == ''

def test_split_cards():
    cards = command.cards_from_query('toil', ORACLE)
    assert len(cards) == 1
    cards = command.cards_from_query('trouble', ORACLE)
    assert len(cards) == 1

    assert command.download_image(cards, ORACLE) != None

    #cards = command.parse_queries('[Toil // Trouble]', ORACLE)
    #assert len(cards) == 1
