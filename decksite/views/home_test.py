import pytest

from decksite.data.archetype import Archetype
from decksite.views.home import biggest_movers


def movers(*changes: float) -> list[Archetype]:
    return [Archetype({'id': i, 'meta_share_change': change}) for i, change in enumerate(changes)]


def test_biggest_movers_shows_the_biggest_risers_and_the_biggest_fallers() -> None:
    all_movers = movers(0.05, 0.04, 0.03, 0.02, 0.01, -0.01, -0.02, -0.03, -0.04, -0.05)

    assert [a.id for a in biggest_movers(all_movers)] == [0, 1, 2, 3, 6, 7, 8, 9]


def test_biggest_movers_ignores_archetypes_that_did_not_move() -> None:
    all_movers = movers(0.05, 0.0, 0.0, -0.05)

    assert [a.id for a in biggest_movers(all_movers)] == [0, 3]


@pytest.mark.parametrize(('changes', 'expected'), [
    # Everything is rising, as in the first week of a season, so show eight risers.
    ((0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01), [0, 1, 2, 3, 4, 5, 6, 7]),
    # Only two fallers, so take six risers rather than leaving two rows empty.
    ((0.06, 0.05, 0.04, 0.03, 0.02, 0.01, -0.01, -0.02), [0, 1, 2, 3, 4, 5, 6, 7]),
    # Only one riser, so take seven fallers.
    ((0.06, -0.01, -0.02, -0.03, -0.04, -0.05, -0.06, -0.07), [0, 1, 2, 3, 4, 5, 6, 7]),
])
def test_biggest_movers_fills_the_table_from_whichever_direction_has_enough(changes: tuple[float, ...], expected: list[int]) -> None:
    assert [a.id for a in biggest_movers(movers(*changes))] == expected


def test_biggest_movers_is_empty_when_nothing_moved() -> None:
    assert biggest_movers([]) == []
