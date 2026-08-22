import pytest

from decksite import prepare
from magic import seasons


def test_season_icon_link_uses_site_colors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seasons, 'current_season_name', lambda: 'Penny Dreadful KLD')

    current = prepare.season_icon_link('KLD')
    previous = prepare.season_icon_link('EMN')

    assert 'class="ss ss-kld season-icon current-season-icon"' in current
    assert 'class="ss ss-emn season-icon"' in previous
    assert 'ss-common' not in previous
    assert 'ss-rare' not in current
    assert 'ss-grad' not in current
