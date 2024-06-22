import pytest

from magic import oracle, seasons
from shared.pd_exception import InvalidDataException


def test_legality() -> None:
    season_name = seasons.current_season_name()
    card = oracle.load_card('Swamp')
    assert card is not None
    assert card.legalities['Standard'] == 'Legal'
    assert card.legalities['Modern'] == 'Legal'
    assert card.legalities['Legacy'] == 'Legal'
    assert card.legalities['Vintage'] == 'Legal'
    assert card.legalities[season_name] == 'Legal'
    card = oracle.load_card('Black Lotus')
    assert card is not None
    assert 'Standard' not in card.legalities.keys()
    assert 'Modern' not in card.legalities.keys()
    assert card.legalities['Legacy'] == 'Banned'
    assert card.legalities['Vintage'] == 'Restricted'
    assert season_name not in card.legalities.keys()


def test_valid_name() -> None:
    assert oracle.valid_name('Dark Ritual') == 'Dark Ritual'
    assert oracle.valid_name('Far/Away') == 'Far // Away'
    assert oracle.valid_name('torrent sculptor') == 'Torrent Sculptor'
    assert oracle.valid_name('Torrent Sculptor // Flamethrower Sonata') == 'Torrent Sculptor'
    assert oracle.valid_name('Torrent Sculptor/Flamethrower Sonata') == 'Torrent Sculptor'
    with pytest.raises(InvalidDataException):
        oracle.valid_name('Definitely // Not a Card /')


def test_load_cards() -> None:
    cards = oracle.load_cards(['Think Twice', 'Swamp'])
    assert len(cards) == 2
    assert 'Think Twice' in [c.name for c in cards]
    assert 'Swamp' in [c.name for c in cards]


def test_deck_sort_x_last() -> None:
    cards = oracle.load_cards(['Ghitu Fire', 'Flash of Insight', 'Frantic Search'])
    assert len(cards) == 3
    cards_by_name = {c.name: c for c in cards}
    assert oracle.deck_sort(cards_by_name['Ghitu Fire']) < oracle.deck_sort(cards_by_name['Flash of Insight'])
    assert oracle.deck_sort(cards_by_name['Ghitu Fire']) > oracle.deck_sort(cards_by_name['Frantic Search'])


# Check that the list of legal cards is being fetched correctly.
@pytest.mark.functional
def test_legality_list() -> None:
    legal_cards = oracle.legal_cards()
    assert len(legal_cards) > 0
