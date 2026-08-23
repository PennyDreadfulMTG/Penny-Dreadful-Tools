import pytest

from decksite.main import APP
from decksite.views.card import Card as CardView
from magic import oracle, seasons
from magic.models import Card, Printing


def test_alternate_card_page_uses_alternate_name_and_printing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seasons, 'current_season_name', lambda: 'Penny Dreadful TST')
    printing = Printing({'set_code': 'om1', 'system_id': 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'})
    monkeypatch.setattr(oracle, 'preferred_printing_for_alternate_name', lambda _card, _name: printing)
    card = Card({
        'name': 'Agent Venom',
        'flavor_names': 'Rhilex the Accursed',
        'layout': 'normal',
        'legalities': None,
        'played_competitively': False,
        'bugs': None,
    })

    with APP.test_request_context('/cards/Rhilex%20the%20Accursed/'):
        view = CardView(card, alternate_name='Rhilex the Accursed')
        content = view.render_content()

    assert view.page_title() == 'Rhilex the Accursed'
    assert card.preferred_printing == 'om1'
    assert card.preferred_printing_system_id == 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'
    assert '<section class="card-image-block">' in content
    assert '<p class="alternate-printing-note ">Alternate printing of' in content
    assert 'href="/cards/Agent%20Venom/">Agent Venom</a>' in content
    assert 'src="/image/Agent Venom/?printing=om1&amp;printing_id=d62cf4f8-36a2-4d9f-9d52-53ea18a52760"' in content
    assert content.index('src="/image/Agent Venom/?printing=om1') < content.index('Alternate printing of')


def test_canonical_card_page_links_to_alternate_printing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seasons, 'current_season_name', lambda: 'Penny Dreadful TST')
    printing = Printing({'set_code': 'om1', 'system_id': 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'})
    monkeypatch.setattr(oracle, 'preferred_printing_for_alternate_name', lambda _card, _name: printing)
    card = Card({
        'name': 'Agent Venom',
        'flavor_names': 'Rhilex the Accursed',
        'layout': 'normal',
        'legalities': None,
        'played_competitively': False,
        'bugs': None,
    })

    with APP.test_request_context('/cards/Agent%20Venom/'):
        view = CardView(card)
        content = view.render_content()

    assert view.page_title() == 'Agent Venom'
    assert '<p class="alternate-printing-note ">Also printed as <a href="/cards/Rhilex%20the%20Accursed/">Rhilex the Accursed</a>.</p>' in content
    assert '<a class="card" href="/cards/Rhilex%20the%20Accursed/">' not in content
    assert content.index('class="card-img ') < content.index('Also printed as')


def test_canonical_card_page_lists_alternate_printings_in_one_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seasons, 'current_season_name', lambda: 'Penny Dreadful TST')
    printing = Printing({'set_code': 'sld', 'system_id': 'sld-id'})
    monkeypatch.setattr(oracle, 'preferred_printing_for_alternate_name', lambda _card, _name: printing)
    card = Card({
        'name': 'Command Tower',
        'flavor_names': 'Croft Manor|Cybertron|The Spire',
        'layout': 'normal',
        'legalities': None,
        'played_competitively': False,
        'bugs': None,
    })

    with APP.test_request_context('/cards/Command%20Tower/'):
        content = CardView(card).render_content()

    assert (
        'Also printed as <a href="/cards/Croft%20Manor/">Croft Manor</a>, '
        '<a href="/cards/Cybertron/">Cybertron</a>, '
        '<a href="/cards/The%20Spire/">The Spire</a>.'
    ) in content
    assert content.count('Also printed as') == 1
