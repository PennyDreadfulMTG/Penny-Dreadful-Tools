import json
from typing import Any, cast

import pytest

from decksite.controllers import api
from decksite.main import APP
from shared.container import Container


def test_status_includes_stale_card_information_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.magic_database, 'card_information_is_available', lambda: True)
    monkeypatch.setattr(api.magic_database, 'stale_card_information_age', lambda: api.datetime.timedelta(days=4))
    monkeypatch.setattr(api.league, 'active_league', lambda: None)

    with APP.test_request_context('/api/status'):
        response = cast(Any, api.person_status).__wrapped__()

    data = json.loads(response.get_data(as_text=True))
    assert data['card_information_warning'] == 'Card data last updated 4 days ago'

def test_status_omits_recent_card_information_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.magic_database, 'card_information_is_available', lambda: True)
    monkeypatch.setattr(api.magic_database, 'stale_card_information_age', lambda: None)
    monkeypatch.setattr(api.league, 'active_league', lambda: None)

    with APP.test_request_context('/api/status'):
        response = cast(Any, api.person_status).__wrapped__()

    data = json.loads(response.get_data(as_text=True))
    assert data['card_information_warning'] == ''

def test_status_reports_unavailable_card_information(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.magic_database, 'card_information_is_available', lambda: False)
    monkeypatch.setattr(api.league, 'active_league', lambda: None)

    with APP.test_request_context('/api/status'):
        response = cast(Any, api.person_status).__wrapped__()

    data = json.loads(response.get_data(as_text=True))
    assert data['card_information_warning'] == 'Card data is unavailable'


def test_archetypes2_serializes_win_percent_as_number_or_null(monkeypatch: pytest.MonkeyPatch) -> None:
    results = [
        Container({'id': 1, 'name': 'Defined', 'wins': 1, 'losses': 1, 'draws': 0, 'win_percent': 50.0}),
        Container({'id': 2, 'name': 'Undefined', 'wins': 0, 'losses': 0, 'draws': 1, 'win_percent': None}),
    ]
    monkeypatch.setattr(api.archs, 'load_disjoint_archetypes', lambda **_kwargs: (results, len(results)))
    monkeypatch.setattr(api.playability, 'key_cards_long', lambda *_args: {})
    monkeypatch.setattr(api.oracle, 'cards_by_name', lambda: {})
    monkeypatch.setattr(api, 'prepare_archetypes_for_api', lambda *_args: None)

    with APP.test_request_context('/api/archetypes2/?seasonId=all'):
        response = api.archetypes2_api()

    data = json.loads(response.get_data(as_text=True))
    assert data['objects'][0]['winPercent'] == 50.0
    assert isinstance(data['objects'][0]['winPercent'], float)
    assert data['objects'][1]['winPercent'] is None
