from collections.abc import Iterable

import pytest

from magic import oracle, seasons
from magic.models import Card
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

def test_valid_name_returns_canonical_name_for_alias_front(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Card({'name': 'Peter Parker', 'flavor_names': 'Surris, Spidersilk Innovator'})
    monkeypatch.setitem(oracle.CARDS_BY_NAME, 'Surris, Spidersilk Innovator', card)
    assert oracle.valid_name('Surris, Spidersilk Innovator // Surris, Silk-Tech Vanguard') == 'Peter Parker'

def test_init_rebuilds_names_and_ignores_alias_collisions(monkeypatch: pytest.MonkeyPatch) -> None:
    canonical = Card({'name': 'Shared Name'})
    aliased = Card({'name': 'Other Card', 'flavor_names': 'Shared Name|Alternate Name'})
    monkeypatch.setattr(oracle, 'CARDS_BY_NAME', {'Stale Alias': aliased})
    monkeypatch.setattr(oracle, 'load_cards', lambda: [canonical, aliased])
    monkeypatch.setattr(oracle, 'load_cards_with_flavor_names', lambda: [aliased])

    oracle.init(force=True)

    assert 'Stale Alias' not in oracle.CARDS_BY_NAME
    assert oracle.CARDS_BY_NAME['Shared Name'] is canonical
    assert oracle.CARDS_BY_NAME['Alternate Name'] is aliased

def test_load_cards() -> None:
    cards = oracle.load_cards(['Think Twice', 'Swamp'])
    assert len(cards) == 2
    assert 'Think Twice' in [c.name for c in cards]
    assert 'Swamp' in [c.name for c in cards]

@pytest.mark.parametrize('names', [[], (), {}, iter(())])
def test_load_cards_empty_iterable(names: Iterable[str]) -> None:
    assert oracle.load_cards(names) == []

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
