import pytest

from decksite.data import card
from decksite.database import db
from shared import perf
from shared.container import Container

INTEGER_STAT_FIELDS = [
    'num_decks',
    'wins',
    'losses',
    'draws',
    'record',
    'perfect_runs',
    'tournament_wins',
    'tournament_top8s',
]


@pytest.mark.perf
def test_load_cards_season() -> None:
    # Trigger missing-preaggregation recovery outside the timer without warming the season under test.
    card.load_cards(season_id=2)
    perf.test(lambda: card.load_cards(season_id=1), 0.5)

@pytest.mark.perf
def test_load_cards_all() -> None:
    perf.test(card.load_cards, 5)


@pytest.mark.functional
def test_load_cards_returns_integer_stats(seeded_db: Container) -> None:
    results = [
        card.load_cards_with_total(limit='LIMIT 1', season_id='all'),
        card.load_cards_with_total(limit='LIMIT 1', competition_id=seeded_db.competition_id),
    ]
    for cards, total in results:
        assert cards
        assert isinstance(total, int)
        for field in INTEGER_STAT_FIELDS:
            assert isinstance(cards[0][field], int), f'{field} was {type(cards[0][field]).__name__}'


@pytest.mark.functional
def test_load_all_legal_cards_returns_zero_integer_stats_for_unplayed_cards(seeded_db: Container) -> None:
    season_id = db().value('SELECT season_id FROM deck_cache LIMIT 1')
    db().execute('CREATE TABLE _legal_cards (season_id INT NOT NULL, name VARCHAR(190) NOT NULL, PRIMARY KEY (season_id, name))')
    db().execute("INSERT INTO _legal_cards (season_id, name) VALUES (%s, 'Plains')", [season_id])

    cards, total = card.load_cards_with_total(season_id=season_id, all_legal=True)

    assert total == 1
    assert len(cards) == 1
    for field in INTEGER_STAT_FIELDS:
        assert cards[0][field] == 0
        assert isinstance(cards[0][field], int)


def test_trailblazer_cards_include_season(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def select(self, sql: str, args: list[int]) -> list[dict[str, str | int]]:
            assert 'deck_cache AS dc' in sql
            assert args == [42]
            return [
                {'card': 'Black Lotus', 'season_id': 1},
                {'card': 'One with Nothing', 'season_id': 2},
            ]

    monkeypatch.setattr(card, 'db', lambda: FakeDatabase())

    assert card.trailblazer_cards(42) == {
        'Black Lotus': 1,
        'One with Nothing': 2,
    }
