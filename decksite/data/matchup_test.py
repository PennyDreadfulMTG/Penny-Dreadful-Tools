import pytest

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
