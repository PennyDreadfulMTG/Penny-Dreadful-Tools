import pytest

from decksite import prepare
from decksite.main import APP
from magic import seasons
from magic.models import Card
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
        {'name': 'Rhilex the Accursed', 'url': '/cards/Rhilex%20the%20Accursed/'},
    ]
    assert '4 Agent Venom' in rendered
    assert 'class="alternate-card-name" title="Alternate printed name">· Rhilex the Accursed</a>' in rendered

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
