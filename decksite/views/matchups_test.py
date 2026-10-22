import pytest

from decksite.data.matchup import MatchupResults
from decksite.main import APP
from decksite.views.matchups import Matchups
from shared_web import template


def matchup_results(wins: int = 2, losses: int = 1, draws: int = 1) -> MatchupResults:
    return MatchupResults(
        num_decks=2,
        num_matches=4,
        wins=wins,
        draws=draws,
        losses=losses,
    )


@pytest.mark.parametrize(('wins', 'losses', 'expected'), [(0, 0, '—'), (0, 1, '0.0'), (2, 1, '66.7')])
def test_matchup_win_percentage_display(monkeypatch: pytest.MonkeyPatch, wins: int, losses: int, expected: str) -> None:
    monkeypatch.setattr(Matchups, 'all_seasons', lambda _self: [])
    results = matchup_results(wins=wins, losses=losses)
    original_percent = results.win_percent
    with APP.test_request_context('/matchups/'):
        view = Matchups({}, {}, None, results)
        html = template.render_name('matchups', view)

    assert f'<td class="n">{expected}</td>' in html
    assert results.win_percent == original_percent


def test_matchup_search_has_open_graph_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Matchups, 'all_seasons', lambda _self: [])
    path = '/matchups/?hero_person_id=1&hero_archetype_id=2&enemy_archetype_id=3&season_id=7'

    with APP.test_request_context(path):
        view = Matchups(
            {'person_id': '1', 'person_name': 'SmokeTester', 'archetype_id': '2', 'archetype_name': 'Aggro'},
            {'archetype_id': '3', 'archetype_name': 'Control'},
            7,
            matchup_results(),
        )

        assert view.og_title() == 'Aggro, SmokeTester versus Control'
        assert view.og_description() == 'Aggro, SmokeTester versus Control is 2–1–1 (66.7% win rate) · Season 7'
        assert view.og_url() == f'http://localhost{path}'


def test_matchup_search_without_matches_still_has_open_graph_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Matchups, 'all_seasons', lambda _self: [])

    with APP.test_request_context('/matchups/?hero_person_id=&hero_card=Black+Lotus'):
        view = Matchups({'card': 'Black Lotus'}, {}, None, matchup_results(wins=0, losses=0, draws=0))

        assert view.og_title() == 'Black Lotus versus All Decks'
        assert view.og_description() == 'Black Lotus versus All Decks is 0–0 · All Time'


def test_matchup_calculator_without_search_has_default_open_graph_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Matchups, 'all_seasons', lambda _self: [])

    with APP.test_request_context('/matchups/'):
        view = Matchups({}, {}, None, None)

        assert view.og_title() == 'Matchups Calculator'
        assert view.og_description() == 'Penny Dreadful is an ultra-budget Magic Online format with thousands of legal cards, free weekly tournaments, a free league, and quarterly rotations.'
        assert view.og_url() == 'http://localhost/matchups/'
