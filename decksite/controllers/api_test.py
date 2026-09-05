import json
from typing import Any, cast

import pytest

from decksite.controllers import api
from decksite.database import db
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


def test_card_api_returns_not_found_for_unknown_card() -> None:
    response = APP.test_client().get('/api/card/DefinitelyNotARealCard/')

    assert response.status_code == 404
    assert response.get_json()['code'] == 'NOTFOUND'


@pytest.mark.functional
def test_aggregate_apis_serialize_integer_stats_as_numbers(seeded_db: Container) -> None:
    season_id = db().value('SELECT season_id FROM deck_cache LIMIT 1')
    cases = [
        ('/api/cards2/', {
            'deckType': 'all', 'page': 0, 'pageSize': 1, 'seasonId': 'all', 'sortBy': 'numDecks', 'sortOrder': 'DESC',
        }, ['numDecks', 'wins', 'losses', 'draws', 'record', 'perfectRuns', 'tournamentWins', 'tournamentTop8s']),
        ('/api/people/', {
            'page': 0, 'pageSize': 1, 'seasonId': 'all', 'sortBy': 'numDecks', 'sortOrder': 'DESC',
        }, ['numDecks', 'wins', 'losses', 'draws', 'record', 'perfectRuns', 'tournamentWins', 'tournamentTop8s', 'numCompetitions']),
        ('/api/archetypes2/', {
            'deckType': 'all', 'page': 0, 'pageSize': 1, 'seasonId': season_id, 'sortBy': 'quality', 'sortOrder': 'AUTO',
        }, ['numDecks', 'numMatches', 'wins', 'losses', 'draws', 'record', 'perfectRuns', 'tournamentWins', 'tournamentTop8s']),
        ('/api/leaderboards/', {
            'page': 0, 'pageSize': 1, 'seasonId': season_id, 'sortBy': 'points', 'sortOrder': 'DESC',
        }, ['numDecks', 'wins', 'points']),
        ('/api/h2h/', {
            'page': 0, 'pageSize': 1, 'personId': seeded_db.person_id, 'seasonId': season_id, 'sortBy': 'numMatches', 'sortOrder': 'DESC',
        }, ['numMatches', 'wins', 'losses', 'draws', 'record']),
    ]

    client = APP.test_client()
    for path, query_string, fields in cases:
        response = client.get(path, query_string=query_string)
        assert response.status_code == 200, path
        data = response.get_json()
        assert data['objects'], path
        for field in fields:
            value = data['objects'][0][field]
            assert isinstance(value, int) and not isinstance(value, bool), f'{path} {field} was {type(value).__name__}'
