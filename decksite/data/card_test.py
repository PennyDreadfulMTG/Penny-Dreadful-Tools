import pytest

from decksite.data import card
from shared import perf


@pytest.mark.perf
def test_played_cards_season() -> None:
    perf.test(lambda: card.played_cards(season_id=1), 0.5)

@pytest.mark.perf
def test_played_cards_person() -> None:
    where = "d.person_id IN (SELECT id FROM person WHERE mtgo_username = 'j_meka')"
    perf.test(lambda: card.played_cards(where), 0.5)

@pytest.mark.perf
def test_played_cards_all() -> None:
    perf.test(card.played_cards, 5)
