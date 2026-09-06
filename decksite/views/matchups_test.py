import pytest

from decksite.data.archetype import Archetype
from decksite.data.matchup import MatchupResults
from decksite.data.person import Person
from decksite.main import APP
from decksite.views.matchups import Matchups


def matchup_results(wins: int = 2, losses: int = 1, draws: int = 1) -> MatchupResults:
    return MatchupResults(
        hero_deck_ids=[1, 2],
        enemy_deck_ids=[3],
        match_ids=[1, 2, 3, 4],
        wins=wins,
        draws=draws,
        losses=losses,
        hero_decks=[],
        matches=[],
    )


def test_matchup_search_has_open_graph_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Matchups, 'all_seasons', lambda _self: [])
    archetypes = [Archetype({'id': 2, 'name': 'Aggro'}), Archetype({'id': 3, 'name': 'Control'})]
    people = [Person({'id': 1, 'name': 'SmokeTester', 'mtgo_username': 'SmokeTester'})]
    path = '/matchups/?hero_person_id=1&hero_archetype_id=2&enemy_archetype_id=3&season_id=7'

    with APP.test_request_context(path):
        view = Matchups(
            {'person_id': '1', 'archetype_id': '2'},
            {'archetype_id': '3'},
            7,
            archetypes,
            people,
            [],
            matchup_results(),
        )

        assert view.og_title() == 'Aggro, SmokeTester versus Control'
        assert view.og_description() == 'Aggro, SmokeTester versus Control is 2–1–1 (66.7% win rate) · Season 7'
        assert view.og_url() == f'http://localhost{path}'


def test_matchup_search_without_matches_still_has_open_graph_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Matchups, 'all_seasons', lambda _self: [])

    with APP.test_request_context('/matchups/?hero_person_id=&hero_card=Black+Lotus'):
        view = Matchups({'card': 'Black Lotus'}, {}, None, [], [], [], matchup_results(wins=0, losses=0, draws=0))

        assert view.og_title() == 'Black Lotus versus All Decks'
        assert view.og_description() == 'Black Lotus versus All Decks is 0–0 · All Time'


def test_matchup_calculator_without_search_has_no_open_graph_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Matchups, 'all_seasons', lambda _self: [])

    with APP.test_request_context('/matchups/'):
        view = Matchups({}, {}, None, [], [], [], None)

        assert view.og_title() is None
        assert view.og_description() is None
        assert view.og_url() is None
