import json
from typing import Any, cast

import pytest

from decksite.controllers import api
from decksite.main import APP


def _patch_archetypes2_api(monkeypatch: pytest.MonkeyPatch, captured: dict[str, str]) -> None:
    def fake_load_disjoint_archetypes(where: str = 'TRUE', **_kwargs: object) -> tuple[list, int]:
        captured['where'] = where
        return [], 0

    monkeypatch.setattr(api.archs, 'load_disjoint_archetypes', fake_load_disjoint_archetypes)
    monkeypatch.setattr(api.playability, 'key_cards_long', lambda _: {})
    monkeypatch.setattr(api.oracle, 'cards_by_name', lambda: {})
    monkeypatch.setattr(api.seasons, 'season_id', lambda *_args, **_kwargs: None)


def test_archetypes2_api_excludes_unclassified_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}
    _patch_archetypes2_api(monkeypatch, captured)

    with APP.test_request_context('/api/archetypes2'):
        api.archetypes2_api()

    assert 'Unclassified' in captured['where']
    assert 'Commander' in captured['where']
    assert 'NOT IN' in captured['where']


def test_archetypes2_api_uses_text_search_when_query_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}
    _patch_archetypes2_api(monkeypatch, captured)

    with APP.test_request_context('/api/archetypes2?q=aggro'):
        api.archetypes2_api()

    assert 'NOT IN' not in captured['where']


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
