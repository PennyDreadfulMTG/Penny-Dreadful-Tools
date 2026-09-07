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


def test_search_api_ranks_mixed_live_results_and_returns_at_most_ten(monkeypatch: pytest.MonkeyPatch) -> None:
    static_items: tuple[api.site_search.SearchResult, ...] = (
        {'name': 'Bolt Reference', 'type': 'Page', 'url': '/bolt-reference/'},
    )
    monkeypatch.setattr(api, 'static_search_items', lambda: static_items)
    monkeypatch.setattr(api.site_search, 'archetype_names', lambda _query: ['Bolt'])
    monkeypatch.setattr(api.site_search, 'card_names', lambda _query: [
        {'name': f'Bolt Card {i}', 'search_name': f'Bolt Card {i}'} for i in range(10)
    ])
    monkeypatch.setattr(api.site_search, 'person_names', lambda _query: ['Lightning Bolt'])

    response = APP.test_client().get('/api/search/?q=bolt')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 10
    assert data[0] == {'name': 'Bolt', 'type': 'Archetype', 'url': '/archetypes/Bolt/'}
    assert data[1] == {'name': 'Bolt Reference', 'type': 'Page', 'url': '/bolt-reference/'}
    assert data[-1] == {'name': 'Bolt Card 7', 'type': 'Card', 'url': '/cards/Bolt%20Card%207/'}


def test_search_api_does_not_load_sources_for_short_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, 'static_search_items', lambda: pytest.fail('A short search should not load any source'))

    response = APP.test_client().get('/api/search/?q=a')

    assert response.status_code == 200
    assert response.get_json() == []


def test_search_api_uses_alias_rank_but_only_returns_public_result_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, 'static_search_items', lambda: ())
    monkeypatch.setattr(api.site_search, 'archetype_names', lambda _query: [])
    monkeypatch.setattr(api.site_search, 'card_names', lambda _query: [
        {'name': 'Lightning Bolt', 'search_name': 'bolt'},
        {'name': 'Bolt Bend', 'search_name': 'Bolt Bend'},
    ])
    monkeypatch.setattr(api.site_search, 'person_names', lambda _query: [])

    response = APP.test_client().get('/api/search/?q=bolt')

    assert response.get_json() == [
        {'name': 'Lightning Bolt', 'type': 'Card', 'url': '/cards/Lightning%20Bolt/'},
        {'name': 'Bolt Bend', 'type': 'Card', 'url': '/cards/Bolt%20Bend/'},
    ]


def test_static_search_items_include_public_menu_and_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    public_child = Container({'name': 'Child', 'url': '/child/', 'permission_required': None, 'submenu': []})
    private_child = Container({'name': 'Private Child', 'url': '/private-child/', 'permission_required': 'admin', 'submenu': []})
    public = Container({'name': 'Public', 'url': '/public/', 'permission_required': None, 'submenu': [public_child, private_child]})
    private = Container({'name': 'Private', 'url': '/private/', 'permission_required': 'admin', 'submenu': []})
    monkeypatch.setitem(api.APP.config, 'menu', lambda: [public, private])
    monkeypatch.setattr(api.fetcher, 'resources', lambda: {'Guides': {'Example': 'https://example.com/'}})
    api.static_search_items.cache_clear()
    try:
        assert api.static_search_items() == (
            {'name': 'Public', 'type': 'Page', 'url': '/public/'},
            {'name': 'Child', 'type': 'Page', 'url': '/child/'},
            {'name': 'Resources – Guides – Example', 'type': 'Resource', 'url': 'https://example.com/'},
        )
    finally:
        api.static_search_items.cache_clear()


def test_matchup_options_api_returns_small_search_results(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [{'name': 'Lightning Bolt', 'value': 'Lightning Bolt'}]
    monkeypatch.setattr(api.mus, 'search_options', lambda option_type, search, person_filter: expected if option_type == 'cards' and search == 'bolt' and person_filter == 'matchups' else [])

    response = APP.test_client().get('/api/matchup-options/cards/?q=bolt')

    assert response.status_code == 200
    assert response.get_json() == expected


def test_matchup_people_options_passes_admin_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, str]] = []

    def search_options(option_type: str, search: str, person_filter: str) -> list[dict[str, str]]:
        calls.append((option_type, search, person_filter))
        return []

    monkeypatch.setattr(api.mus, 'search_options', search_options)

    response = APP.test_client().get('/api/matchup-options/people/?q=smoke&personFilter=discord')

    assert response.status_code == 200
    assert calls == [('people', 'smoke', 'discord')]


def test_matchup_people_options_rejects_unknown_filter() -> None:
    response = APP.test_client().get('/api/matchup-options/people/?q=smoke&personFilter=anything')

    assert response.status_code == 400


def test_decks_api_combines_standard_and_opponent_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def load_decks_with_total(**kwargs: Any) -> tuple[list[Container], int]:
        captured.update(kwargs)
        return [Container({'id': 7})], 123

    monkeypatch.setattr(api.deck, 'load_decks_with_total', load_decks_with_total)
    monkeypatch.setattr(api, 'prepare_decks', lambda _decks: None)

    response = APP.test_client().get('/api/decks/', query_string={
        'archetypeId': '4',
        'opponentCardName': 'Counterspell',
        'page': '2',
        'pageSize': '20',
        'seasonId': 'all',
    })

    assert response.status_code == 200
    assert response.get_json() == {'objects': [{'id': 7}], 'page': 2, 'total': 123}
    assert 'd.archetype_id IN' in captured['where']
    assert 'd.retired' in captured['where']
    assert 'matchup_enemy.id IN' in captured['where']
    assert "card = 'Counterspell'" in captured['where']
    assert captured['limit'] == 'LIMIT 40, 20'
    assert captured['season_id'] is None


def test_matches_api_combines_hero_and_opponent_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def load_matches_with_total(**kwargs: Any) -> tuple[list[Container], int]:
        captured.update(kwargs)
        return [Container({'id': 8})], 456

    monkeypatch.setattr(api.match, 'load_matches_with_total', load_matches_with_total)
    monkeypatch.setattr(api, 'prepare_matches', lambda _matches: None)

    response = APP.test_client().get('/api/matches/', query_string={
        'personId': '10',
        'opponentPersonId': '11',
        'page': '1',
        'pageSize': '100',
        'seasonId': 'all',
    })

    assert response.status_code == 200
    assert response.get_json() == {'objects': [{'id': 8}], 'page': 1, 'total': 456}
    assert 'd.person_id = 10' in captured['where']
    assert 'od.person_id = 11' in captured['where']
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
