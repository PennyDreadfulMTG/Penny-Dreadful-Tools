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
