import json
from typing import Any, cast

import pytest

from decksite.controllers import api
from decksite.main import APP


def test_status_includes_stale_card_information_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.magic_database, 'stale_card_information_age', lambda: api.datetime.timedelta(days=4))
    monkeypatch.setattr(api.league, 'active_league', lambda: None)

    with APP.test_request_context('/api/status'):
        response = cast(Any, api.person_status).__wrapped__()

    data = json.loads(response.get_data(as_text=True))
    assert data['card_information_warning'] == 'Card data last updated 4 days ago'

def test_status_omits_recent_card_information_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.magic_database, 'stale_card_information_age', lambda: None)
    monkeypatch.setattr(api.league, 'active_league', lambda: None)

    with APP.test_request_context('/api/status'):
        response = cast(Any, api.person_status).__wrapped__()

    data = json.loads(response.get_data(as_text=True))
    assert data['card_information_warning'] == ''
