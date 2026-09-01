from collections.abc import Iterable
from unittest.mock import AsyncMock

import pytest

from magic import oracle, seasons
from magic.models import Card, Printing
from shared.pd_exception import DatabaseException, InvalidDataException


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

def test_official_alternate_names_prefers_combined_double_faced_name() -> None:
    card = Card({
        'name': 'Peter Parker',
        'flavor_names': 'Surris, Silk-Tech Vanguard|Surris, Spidersilk Innovator // Surris, Silk-Tech Vanguard|Surris, Spidersilk Innovator',
    })

    assert oracle.official_alternate_names(card) == [
        'Surris, Spidersilk Innovator // Surris, Silk-Tech Vanguard',
    ]

def test_matching_official_alternate_name_supports_exact_and_unique_prefix() -> None:
    card = Card({'name': 'Agent Venom', 'flavor_names': 'Rhilex the Accursed'})

    assert oracle.matching_official_alternate_name(card, 'Rhilex the Accursed') == 'Rhilex the Accursed'
    assert oracle.matching_official_alternate_name(card, 'rhil', allow_prefix=True) == 'Rhilex the Accursed'
    assert oracle.matching_official_alternate_name(card, 'Agent Venom') is None

def test_preferred_printing_uses_matching_flavor_name(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Card({'id': 1, 'name': 'Zilortha, Strength Incarnate'})
    printings = [
        Printing({
            'set_code': 'iko',
            'system_id': '1c48ddf5-c2da-4fbc-95f2-8a3f2f5737ba',
            'flavor_name': None,
        }),
        Printing({
            'set_code': 'iko',
            'system_id': '9a0639a0-c898-4a07-975c-a02bdd53175b',
            'flavor_name': 'Godzilla, King of the Monsters',
        }),
    ]
    monkeypatch.setattr(oracle, 'get_printings', lambda _card: printings)

    printing = oracle.preferred_printing_for_alternate_name(card, 'Godzilla, King of the Monsters')

    assert printing is not None
    assert printing.system_id == '9a0639a0-c898-4a07-975c-a02bdd53175b'

def test_preferred_printing_uses_omenpaths_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Card({'id': 1, 'name': 'Agent Venom'})
    printings = [
        Printing({'set_code': 'spm', 'system_id': 'spm-id', 'flavor_name': None}),
        Printing({'set_code': 'om1', 'system_id': 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760', 'flavor_name': None}),
    ]
    monkeypatch.setattr(oracle, 'get_printings', lambda _card: printings)

    printing = oracle.preferred_printing_for_alternate_name(card, 'Rhilex the Accursed')

    assert printing is not None
    assert printing.set_code == 'om1'
    assert printing.system_id == 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'

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

def test_init_indexes_back_face_names(monkeypatch: pytest.MonkeyPatch) -> None:
    transform_card = Card({'name': 'The Irencrag', 'names': 'The Irencrag|Irencrag'})
    monkeypatch.setattr(oracle, 'CARDS_BY_NAME', {})
    monkeypatch.setattr(oracle, 'load_cards', lambda: [transform_card])
    monkeypatch.setattr(oracle, 'load_cards_with_flavor_names', lambda: [])

    oracle.init(force=True)

    assert oracle.CARDS_BY_NAME['The Irencrag'] is transform_card
    assert oracle.CARDS_BY_NAME['Irencrag'] is transform_card

def test_init_back_face_does_not_override_existing_front_face(monkeypatch: pytest.MonkeyPatch) -> None:
    front_card = Card({'name': 'Irencrag'})
    transform_card = Card({'name': 'The Irencrag', 'names': 'The Irencrag|Irencrag'})
    monkeypatch.setattr(oracle, 'CARDS_BY_NAME', {})
    monkeypatch.setattr(oracle, 'load_cards', lambda: [front_card, transform_card])
    monkeypatch.setattr(oracle, 'load_cards_with_flavor_names', lambda: [])

    oracle.init(force=True)

    assert oracle.CARDS_BY_NAME['Irencrag'] is front_card

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

@pytest.mark.asyncio
async def test_scryfall_import_async_handles_duplicate_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    sfcard = {'object': 'card', 'name': 'Waterlogged Teachings // Inundated Archive'}
    monkeypatch.setattr('magic.oracle.fetch_tools.fetch_json_async', AsyncMock(return_value=sfcard))

    def raise_invalid(name: str) -> str:
        raise InvalidDataException('not found')
    monkeypatch.setattr('magic.oracle.valid_name', raise_invalid)

    duplicate_exc = DatabaseException("Failed to execute ... because of (1062, \"Duplicate entry 'x' for key 'oracle_id'\")")
    monkeypatch.setattr('magic.oracle.add_cards_and_update_async', AsyncMock(side_effect=duplicate_exc))

    result = await oracle.scryfall_import_async('Waterlogged Teachings')

    assert result is False

# Check that the list of legal cards is being fetched correctly.
@pytest.mark.functional
def test_legality_list() -> None:
    legal_cards = oracle.legal_cards()
    assert len(legal_cards) > 0
