import pytest

from decksite import prepare
from decksite.data.archetype import Archetype
from decksite.main import APP
from magic import seasons
from magic.models import Card, Printing
from shared_web import template


def test_season_icon_link_uses_site_colors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seasons, 'current_season_name', lambda: 'Penny Dreadful KLD')

    current = prepare.season_icon_link('KLD')
    previous = prepare.season_icon_link('EMN')

    assert 'class="season-icon-link current-season-icon"' in current
    assert 'class="season-icon-link"' in previous
    assert 'title="Current season"' in current
    assert 'title="Current season"' not in previous
    assert 'class="ss ss-kld season-icon"' in current
    assert 'class="ss ss-emn season-icon"' in previous
    assert 'current-season-icon' not in previous
    assert 'ss-common' not in previous
    assert 'ss-rare' not in current
    assert 'ss-grad' not in current


def test_prepare_card_adds_official_alternate_name_links(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seasons, 'current_season_name', lambda: 'Penny Dreadful TST')
    printing = Printing({'set_code': 'om1', 'system_id': 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'})
    monkeypatch.setattr(prepare.oracle, 'preferred_printing_for_alternate_name', lambda _card, _name: printing)
    card = Card({
        'name': 'Agent Venom',
        'flavor_names': 'Rhilex the Accursed',
        'layout': 'normal',
        'legalities': None,
    })

    with APP.test_request_context('/'):
        prepare.prepare_card(card)
        rendered = template.render_name('entry', {'name': card.name, 'n': 4, 'card': card})

    assert card.alternate_printed_names == [
        {
            'name': 'Rhilex the Accursed',
            'url': '/cards/Rhilex%20the%20Accursed/',
            'separator': '',
        },
    ]
    assert card.decklist_alternate_printed_names == card.alternate_printed_names
    assert '4 Agent Venom' in rendered
    assert 'class="alternate-card-name">· Rhilex the Accursed</a>' in rendered
    assert 'class="card alternate-card-name"' not in rendered


def test_prepare_card_omits_non_omenpaths_names_from_decklists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seasons, 'current_season_name', lambda: 'Penny Dreadful TST')
    printing = Printing({'set_code': 'sld', 'system_id': 'a49bdd0b-fc8d-4706-b614-14d1731fddc0'})
    monkeypatch.setattr(prepare.oracle, 'preferred_printing_for_alternate_name', lambda _card, _name: printing)
    card = Card({
        'name': 'Phantasmal Image',
        'flavor_names': 'Absolutely Accurate Actor',
        'layout': 'normal',
        'legalities': None,
    })

    with APP.test_request_context('/'):
        prepare.prepare_card(card)
        rendered = template.render_name('entry', {'name': card.name, 'n': 4, 'card': card})

    assert card.alternate_printed_names == [
        {
            'name': 'Absolutely Accurate Actor',
            'url': '/cards/Absolutely%20Accurate%20Actor/',
            'separator': '',
        },
    ]
    assert card.decklist_alternate_printed_names == []
    assert 'Absolutely Accurate Actor' not in rendered

def test_prepare_card_uses_preferred_printing_for_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seasons, 'current_season_name', lambda: 'Penny Dreadful TST')
    card = Card({
        'name': 'Agent Venom',
        'layout': 'normal',
        'legalities': None,
        'preferred_printing': 'om1',
        'preferred_printing_system_id': 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760',
    })

    with APP.test_request_context('/'):
        prepare.prepare_card(card)

    assert card.img_url == '/image/Agent Venom/?printing=om1&printing_id=d62cf4f8-36a2-4d9f-9d52-53ea18a52760'


def test_prepare_archetypes_for_api_adds_grid_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    archetypes = [
        Archetype({'id': 1, 'name': 'Populated', 'wins': None, 'losses': 2, 'draws': 3, 'num_decks': 1}),
        Archetype({'id': 2, 'name': 'Empty', 'wins': None, 'losses': None, 'draws': None, 'num_decks': 0}),
    ]
    cards = {
        'Plains': Card({'name': 'Plains', 'type_line': 'Basic Land — Plains', 'oracle_text': '', 'mana_cost': None}),
        **{
            f'Card {n}': Card({'name': f'Card {n}', 'type_line': 'Creature', 'oracle_text': '', 'mana_cost': '{R}'})
            for n in range(1, 7)
        },
    }
    key_card_names = {1: list(cards)}
    colors_calls: list[list[str]] = []

    def fake_find_colors(key_cards: list[Card]) -> tuple[list[str], list[str]]:
        colors_calls.append([card.name for card in key_cards])
        return (['R'], ['R']) if key_cards else ([], [])

    monkeypatch.setattr(prepare, 'find_colors', fake_find_colors)
    monkeypatch.setattr(prepare.image_fetcher, 'scryfall_image', lambda card, version: f'https://images.test/{card.name}/{version}')

    with APP.test_request_context('/'):
        prepare.prepare_archetypes_for_api(archetypes, key_card_names, cards, False, 42)

    assert [(card.name, card.url) for card in archetypes[0].key_cards] == [
        (f'Card {n}', f'https://images.test/Card {n}/art_crop') for n in range(1, 6)
    ]
    assert archetypes[0].num_matches == 5
    assert archetypes[0].colors_safe == '<div class="mana-bar"><span class="stacked-bar mana-R" style="flex-grow: 100"></span></div>'
    assert archetypes[1].key_cards == []
    assert archetypes[1].num_matches == 0
    assert archetypes[1].colors_safe == '<div class="mana-bar"><span class="stacked-bar mana" style="flex-grow: 1"></span></div>'
    assert colors_calls == [list(cards), []]
