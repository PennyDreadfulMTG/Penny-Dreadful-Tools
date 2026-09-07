import pytest

from decksite.data import matchup, person
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
        num_decks=2,
        num_matches=3,
        wins=wins,
        draws=0,
        losses=losses,
    )

    assert results.win_percent == expected
    assert results.win_percent is None or isinstance(results.win_percent, float)


def test_matchup_counts_results_without_concatenating_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def select(self, sql: str) -> list[dict[str, int]]:
            assert 'COUNT(DISTINCT d.id) AS num_decks' in sql
            assert 'COUNT(DISTINCT m.id) AS num_matches' in sql
            assert 'GROUP_CONCAT' not in sql
            assert 'd.archetype_id IN' in sql
            assert 'od.person_id' in sql
            return [{'num_decks': 12, 'num_matches': 34, 'wins': 20, 'draws': 1, 'losses': 13}]

    monkeypatch.setattr(matchup, 'db', FakeDatabase)

    result = matchup.matchup({'archetype_id': '5'}, {'person_id': '9'}, season_id=43)

    assert result == MatchupResults(num_decks=12, num_matches=34, wins=20, draws=1, losses=13)


def test_opponent_decks_where_filters_through_matches() -> None:
    where = matchup.opponent_decks_where({'person_id': '1', 'card': "Urza's Bauble"})

    assert 'EXISTS' in where
    assert 'matchup_dm.deck_id = d.id' in where
    assert 'matchup_enemy.person_id = 1' in where
    assert "card = 'Urza''s Bauble'" in where


@pytest.mark.parametrize(
    ('option_type', 'expected_table'),
    [
        ('archetypes', 'FROM archetype'),
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


@pytest.mark.parametrize(
    ('person_filter', 'expected_where'),
    [
        ('matchups', 'p.mtgo_username IS NOT NULL'),
        ('all', 'TRUE'),
        ('discord', 'p.discord_id IS NOT NULL'),
        ('unbanned', 'NOT COALESCE(p.banned, FALSE)'),
    ],
)
def test_search_people_returns_identifiable_lightweight_matches(person_filter: person.PersonFilter, expected_where: str, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def select(self, sql: str, args: list[str | int]) -> list[dict[str, object]]:
            assert 'FROM person AS p' in sql
            assert expected_where in sql
            assert args == ['%Smoke%', 'Smoke%', 'Smoke%', 'Smoke%', 'Smoke%', 'Smoke%', 10]
            return [{
                'value': '123',
                'name': 'smoketester',
                'mtgo_username': 'SmokeTester',
                'site_name': 'Smoke',
                'tappedout_username': 'SmokeTO',
                'mtggoldfish_username': None,
                'discord_id': 456,
            }]

    monkeypatch.setattr(person, 'db', FakeDatabase)

    options = person.search_options('Smoke', person_filter=person_filter)

    assert options == [{'value': '123', 'name': 'smoketester', 'label': 'SmokeTester (to:SmokeTO, discord:456)'}]


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
