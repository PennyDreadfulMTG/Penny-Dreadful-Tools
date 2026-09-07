import pytest

from decksite.data import matchup
from decksite.data.matchup import MatchupResults


@pytest.mark.parametrize(
    ('wins', 'losses', 'expected'),
    [
        (1, 1, 50.0),
        (0, 0, None),
    ],
)
def test_win_percent_is_float_or_none(wins: int, losses: int, expected: float | None) -> None:
    results = MatchupResults(
        hero_deck_ids=[],
        enemy_deck_ids=[],
        match_ids=[],
        wins=wins,
        draws=0,
        losses=losses,
        hero_decks=[],
        matches=[],
    )

    assert results.win_percent == expected
    assert results.win_percent is None or isinstance(results.win_percent, float)


@pytest.mark.parametrize(
    ('option_type', 'expected_table'),
    [
        ('archetypes', 'FROM archetype'),
        ('people', 'FROM person'),
        ('cards', 'FROM _card_stats'),
    ],
)
def test_search_options_returns_lightweight_matches(option_type: matchup.MatchupOptionType, expected_table: str, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def select(self, sql: str, args: list[str | int]) -> list[dict[str, str]]:
            assert expected_table in sql
            assert args == ['%Bolt%', 'Bolt%', 10]
            return [{'value': '123', 'name': 'Lightning Bolt'}]

    monkeypatch.setattr(matchup, 'db', FakeDatabase)

    options = matchup.search_options(option_type, 'Bolt')

    assert options == [{'value': '123', 'name': 'Lightning Bolt'}]


def test_search_options_ignores_an_empty_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(matchup, 'db', lambda: pytest.fail('An empty search should not query the database'))

    assert matchup.search_options('cards', ' ') == []


def test_resolve_choices_supports_typed_names(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def select(self, sql: str, args: list[str]) -> list[dict[str, str | int]]:
            if 'FROM archetype' in sql:
                assert args == ['Aggro']
                return [{'id': 16, 'name': 'Aggro'}]
            assert 'FROM person' in sql
            assert args == ['SmokeTester']
            return [{'id': 42, 'name': 'smoketester', 'label': 'smoketester'}]

        def value(self, sql: str, args: list[str]) -> str:
            assert 'FROM _card_stats' in sql
            assert args == ['Lightning Bolt']
            return 'Lightning Bolt'

    monkeypatch.setattr(matchup, 'db', FakeDatabase)
    choices = matchup.resolve_choices({
        'archetype_name': 'Aggro',
        'person_name': 'SmokeTester',
        'card_name': 'Lightning Bolt',
    })

    assert choices == {
        'archetype_id': '16',
        'archetype_name': 'Aggro',
        'person_id': '42',
        'person_name': 'smoketester',
        'person_label': 'smoketester',
        'card': 'Lightning Bolt',
    }
