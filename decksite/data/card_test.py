import pytest

from decksite.data import card
from shared import perf


@pytest.mark.perf
def test_load_cards_season() -> None:
    # Trigger missing-preaggregation recovery outside the timer without warming the season under test.
    card.load_cards(season_id=2)
    perf.test(lambda: card.load_cards(season_id=1), 0.5)

@pytest.mark.perf
def test_load_cards_all() -> None:
    perf.test(card.load_cards, 5)

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
