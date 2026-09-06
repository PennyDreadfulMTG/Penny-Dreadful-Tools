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


def test_matchup_options_api_returns_small_search_results(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [{'name': 'Lightning Bolt', 'value': 'Lightning Bolt'}]
    monkeypatch.setattr(api.mus, 'search_options', lambda option_type, search: expected if option_type == 'cards' and search == 'bolt' else [])

    response = APP.test_client().get('/api/matchup-options/cards/?q=bolt')

    assert response.status_code == 200
    assert response.get_json() == expected


def test_matchup_decks_api_passes_filters_and_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def load_decks_with_total(hero: dict[str, str], enemy: dict[str, str], **kwargs: Any) -> tuple[list[Container], int]:
        captured.update({'hero': hero, 'enemy': enemy} | kwargs)
        return [Container({'id': 7})], 123

    monkeypatch.setattr(api.mus, 'load_decks_with_total', load_decks_with_total)
    monkeypatch.setattr(api, 'prepare_decks', lambda _decks: None)

    response = APP.test_client().get('/api/matchup-decks/', query_string={
        'heroArchetypeId': '4',
        'enemyCard': 'Counterspell',
        'page': '2',
        'pageSize': '20',
        'seasonId': '43',
    })

    assert response.status_code == 200
    assert response.get_json() == {'objects': [{'id': 7}], 'page': 2, 'total': 123}
    assert captured['hero'] == {'archetype_id': '4'}
    assert captured['enemy'] == {'card': 'Counterspell'}
    assert captured['limit'] == 'LIMIT 40, 20'
    assert captured['season_id'] == 43


def test_matchup_matches_api_returns_a_page_of_read_only_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def load_matches_with_total(hero: dict[str, str], enemy: dict[str, str], **kwargs: Any) -> tuple[list[Container], int]:
        captured.update({'hero': hero, 'enemy': enemy} | kwargs)
        return [Container({'id': 8})], 456

    monkeypatch.setattr(api.mus, 'load_matches_with_total', load_matches_with_total)
    monkeypatch.setattr(api, 'prepare_matches', lambda _matches: None)

    response = APP.test_client().get('/api/matchup-matches/', query_string={
        'heroPersonId': '10',
        'enemyPersonId': '11',
        'page': '1',
        'pageSize': '100',
    })

    assert response.status_code == 200
    assert response.get_json() == {'objects': [{'id': 8}], 'page': 1, 'total': 456}
    assert captured['hero'] == {'person_id': '10'}
    assert captured['enemy'] == {'person_id': '11'}
    assert captured['limit'] == 'LIMIT 100, 100'
    assert captured['season_id'] is None


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
