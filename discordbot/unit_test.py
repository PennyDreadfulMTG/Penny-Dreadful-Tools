import os

import pytest

from discordbot import command, emoji
from magic import image_fetcher, oracle, seasons
from magic.models import Card
from shared import configuration, fetch_tools


# Check that we can fetch card images.
@pytest.mark.functional
def test_imagedownload() -> None:
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='island.jpg')
    if fetch_tools.acceptable_file(filepath):
        os.remove(filepath)
    c = [oracle.load_card('Island')]
    assert image_fetcher.download_image(c) is not None


# Check that we can fall back to the Gatherer images if all else fails.
# Note: bluebones doesn't have Nalathni Dragon, while Gatherer does, which makes it useful here.
@pytest.mark.functional
def test_fallbackimagedownload() -> None:
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename='nalathni-dragon.jpg')
    if fetch_tools.acceptable_file(filepath):
        os.remove(filepath)
    c = [oracle.load_card('Nalathni Dragon')]
    assert image_fetcher.download_image(c) is not None


# Check that we can succesfully fail at getting an image.
@pytest.mark.functional
def test_noimageavailable() -> None:
    c = Card({'name': 'Made Up Card Name', 'id': 0, 'multiverseid': 0, 'names': 'Made Up Card Name', 'layout': 'normal'})
    assert image_fetcher.download_image([c]) is None


# Search for a single card via full name,
def test_solo_query() -> None:
    names = command.parse_queries('[Gilder Bairn]', False)
    assert len(names) == 1
    assert names[0] == 'gilder bairn'
    results = command.results_from_queries(names)
    assert len(results) == 1


# Two cards, via full name
def test_double_query() -> None:
    names = command.parse_queries('[Mother of Runes] [Ghostfire]', False)
    assert len(names) == 2
    results = command.results_from_queries(names)
    assert len(results) == 2


def test_compat() -> None:
    names = command.parse_queries('[[Mother of Runes]]', True)
    assert len(names) == 0


# The following two sets assume that Ertai is a long dead character, and is getting no new cards.
# This was a bad assumption, and DMU broke these tests.  We should find safer test cases.
def test_legend_query() -> None:
    names = command.parse_queries('[Ertai]', False)
    assert len(names) == 1
    results = command.results_from_queries(names)[0][0]
    assert len(results.get_ambiguous_matches()) == 3


def test_partial_query() -> None:
    names = command.parse_queries("[Ertai's]", False)
    assert len(names) == 1
    results = command.results_from_queries(names)[0][0]
    assert len(results.get_ambiguous_matches()) == 4


def test_info_emoji() -> None:
    legal_cards = oracle.legal_cards()
    assert len(legal_cards) > 0
    legal_card = oracle.load_card('island')
    assert emoji.info_emoji(legal_card, no_rotation_hype=True) == ':white_check_mark:'
    illegal_card = oracle.load_card('black lotus')
    assert emoji.info_emoji(illegal_card, no_rotation_hype=True) == ':no_entry_sign:'
    assert emoji.info_emoji(illegal_card, verbose=True, no_rotation_hype=True) == f':no_entry_sign: (not legal in {seasons.current_season_name()})'


def test_accents() -> None:
    c = oracle.load_card('Lim-Dûl the Necromancer')
    assert c is not None
    c = oracle.load_card('Séance')
    assert c is not None
    c = oracle.load_card('Lim-Dul the Necromancer')
    assert c is not None
    c = oracle.load_card('Seance')
    assert c is not None


def test_aether() -> None:
    c = oracle.load_card('aether Spellbomb')
    assert c is not None


def test_split_cards() -> None:
    cards = oracle.load_cards(['Armed // Dangerous'])
    assert len(cards) == 1
    assert image_fetcher.download_image(cards) is not None
    names = command.parse_queries('[Toil // Trouble]', False)
    assert len(names) == 1
    results = command.results_from_queries(names)
    assert len(results) == 1


# This is really a test of the multiverse import process, but make sure things get the right CMC.
def test_cmc() -> None:
    card = oracle.load_card('Odds // Ends')
    assert card.cmc == 7
    card = oracle.load_card('Ancestral Vision')
    assert card.cmc == 0
    card = oracle.load_card('Delver of Secrets')
    assert card.cmc == 1
    card = oracle.load_card('Gisela, the Broken Blade')
    assert card.cmc == 4
    card = oracle.load_card('Budoka Gardener')
    assert card.cmc == 2
    card = oracle.load_card('Driven // Despair')
    assert card.cmc == 4
