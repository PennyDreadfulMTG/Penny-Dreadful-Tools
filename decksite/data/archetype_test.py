from decimal import Decimal
from typing import Any
from unittest import mock

import pytest

from decksite.data import archetype, clauses
from decksite.database import db
from decksite.testutil import with_test_db
from shared.pd_exception import DoesNotExistException
from shared.text import merge_slashes


class FakeDatabase:
    def __init__(self) -> None:
        self.sql = ''
        self.args: list[Any] = []

    def select(self, sql: str, args: list[Any]) -> list[dict[str, Any]]:
        self.sql = sql
        self.args = args
        return [
            {'meta_share': Decimal('0.125'), 'win_rate': Decimal('0.6')},
            {'meta_share': None, 'win_rate': None},
        ]


@pytest.mark.parametrize(('tournament_only', 'where'), [(False, 'TRUE'), (True, "deck_type = 'tournament'")])
def test_season_stats(monkeypatch: pytest.MonkeyPatch, tournament_only: bool, where: str) -> None:
    database = FakeDatabase()
    monkeypatch.setattr(archetype, 'db', lambda: database)

    assert archetype.season_stats(42, tournament_only) == [
        {'meta_share': 0.125, 'win_rate': 0.6},
        {'meta_share': 0.0, 'win_rate': None},
    ]
    assert database.args == [42]
    assert f'AND {where}' in database.sql


def test_assign_clears_cached_deck_after_committing(monkeypatch: pytest.MonkeyPatch) -> None:
    database = mock.Mock()
    clear = mock.Mock()
    monkeypatch.setattr(archetype, 'db', lambda: database)
    monkeypatch.setattr(archetype.redis, 'clear', clear)

    archetype.assign(42, 7, None, False, 72)

    database.commit.assert_called_once_with('assign_archetype')
    clear.assert_called_once_with('decksite:deck:42')


@with_test_db
@pytest.mark.functional
def test_load_disjoint_archetypes_returns_float_or_none_for_win_percent() -> None:
    archetype.preaggregate_disjoint_archetypes()
    db().execute("""
        INSERT INTO _arch_disjoint_stats
            (archetype_id, season_id, num_decks, wins, losses, draws, perfect_runs, tournament_wins, tournament_top8s, deck_type)
        VALUES
            (1, 1, 3, 2, 1, 0, 0, 0, 0, 'league'),
            (2, 1, 1, 0, 0, 1, 0, 0, 0, 'league'),
            (3, 1, 4, 1, 3, 0, 0, 0, 0, 'league'),
            (4, 1, 4, 3, 1, 0, 0, 0, 0, 'league')
    """)

    ascending, _ = archetype.load_disjoint_archetypes(order_by=clauses.archetype_order_by('winPercent', 'ASC'), season_id=1)
    descending, _ = archetype.load_disjoint_archetypes(order_by=clauses.archetype_order_by('winPercent', 'DESC'), season_id=1)
    win_percent_by_id = {a.id: a.win_percent for a in ascending}

    assert [a.id for a in ascending] == [3, 1, 4, 2]
    assert [a.id for a in descending] == [4, 1, 3, 2]
    assert win_percent_by_id[1] == 66.7
    assert isinstance(win_percent_by_id[1], float)
    assert win_percent_by_id[2] is None


@with_test_db
@pytest.mark.functional
@pytest.mark.parametrize('sort_by', ['quality', 'qualityOptimistic', 'qualityStrict', 'potential'])
def test_archetype_quality_sorts_put_no_match_archetypes_last(sort_by: str) -> None:
    archetype.preaggregate_disjoint_archetypes()
    db().execute("""
        INSERT INTO _arch_disjoint_stats
            (archetype_id, season_id, num_decks, wins, losses, draws, perfect_runs, tournament_wins, tournament_top8s, deck_type)
        VALUES
            (1, 1, 3, 2, 1, 0, 0, 0, 0, 'league'),
            (2, 1, 1, 0, 0, 1, 0, 0, 0, 'league'),
            (3, 1, 4, 1, 3, 0, 0, 0, 0, 'league'),
            (4, 1, 4, 3, 1, 0, 0, 0, 0, 'league')
    """)

    ascending, _ = archetype.load_disjoint_archetypes(order_by=clauses.archetype_order_by(sort_by, 'ASC'), season_id=1)
    descending, _ = archetype.load_disjoint_archetypes(order_by=clauses.archetype_order_by(sort_by, 'DESC'), season_id=1)

    assert ascending[-1].id == 2
    assert descending[-1].id == 2


@with_test_db
@pytest.mark.functional
def test_load_movers_and_shakers_compares_the_last_week_to_the_week_before() -> None:
    archetype.preaggregate_archetype_days()
    day = 86400
    latest = 100 * day
    db().execute(f"""
        INSERT INTO _arch_day_stats
            (archetype_id, season_id, day, num_decks, wins, losses, draws, deck_type)
        VALUES
            -- Riser: no matches in the first week, the largest share of them in the second.
            (1, 1, {latest - day * 10}, 1, 0, 0, 0, 'league'),
            (1, 1, {latest}, 5, 6, 4, 0, 'league'),
            -- Faller: most of the matches in the first week, a quarter of them in the second.
            (2, 1, {latest - day * 10}, 5, 5, 5, 0, 'league'),
            (2, 1, {latest}, 2, 3, 3, 0, 'league'),
            -- Steady: the same number of matches in both weeks.
            (3, 1, {latest - day * 10}, 5, 3, 3, 0, 'league'),
            (3, 1, {latest}, 5, 3, 3, 0, 'league'),
            -- Below the minimum match count in both weeks, so not a mover, but still part of the
            -- metagame everything else is a share of.
            (4, 1, {latest}, 1, 1, 0, 0, 'league')
    """)

    movers = archetype.load_movers_and_shakers(1, min_matches=6)

    assert [a.id for a in movers] == [1, 3, 2]
    assert [round(float(a.meta_share_change), 3) for a in movers] == [0.435, -0.114, -0.364]
    assert movers[0].wins == 6
    assert movers[0].losses == 4
    assert movers[0].win_percent == 60.0


@pytest.mark.parametrize(('a', 'b'), [
    ('Leave // Chance Midrange', 'Leave / Chance Midrange'),   # What the proxies send after merging slashes.
    ('Leave // Chance Midrange', 'Leave/Chance Midrange'),
    ('Leave // Chance Midrange', 'leave // chance midrange'),
    ('Leave // Chance Midrange', 'Leave-//-Chance-Midrange'),  # Dashes stand in for spaces.
    ('Séance', 'Seance'),                                      # utf8mb4_unicode_ci ignored accents; so must we.
    ('-1/-1 Counters', '-1/-1 Counters'),
])
def test_url_name_key_treats_these_as_the_same_name(a: str, b: str) -> None:
    assert archetype.url_name_key(a) == archetype.url_name_key(b)


@pytest.mark.parametrize(('a', 'b'), [
    ('Leave // Chance Midrange', 'Arrive // Fortune Midrange'),
    ('-1/-1 Counters', '+1/+1 Counters'),
    ('Aggro', 'Aggro Control'),
])
def test_url_name_key_keeps_these_apart(a: str, b: str) -> None:
    assert archetype.url_name_key(a) != archetype.url_name_key(b)


@with_test_db
@pytest.mark.functional
@pytest.mark.parametrize('url_name', [
    'Leave // Chance Midrange',
    'Leave / Chance Midrange',
    'Leave/Chance Midrange',
    'leave // chance midrange',
    'Leave-//-Chance-Midrange',
])
def test_load_archetype_finds_name_containing_slashes(url_name: str) -> None:
    """#15124 made these URLs route, but the two sides normalised slashes differently so the lookup still missed."""
    db().execute("INSERT INTO archetype (name, description) VALUES ('Leave // Chance Midrange', '')")

    assert archetype.load_archetype(merge_slashes(url_name)).name == 'Leave // Chance Midrange'


@with_test_db
@pytest.mark.functional
def test_load_movers_and_shakers_does_not_compare_across_a_rotation() -> None:
    archetype.preaggregate_archetype_days()
    day = 86400
    latest = 100 * day
    db().execute(f"""
        INSERT INTO _arch_day_stats
            (archetype_id, season_id, day, num_decks, wins, losses, draws, deck_type)
        VALUES
            (1, 1, {latest - day * 10}, 5, 10, 10, 0, 'league'),
            (1, 1, {latest}, 5, 5, 5, 0, 'league'),
            (2, 2, {latest - day * 10}, 5, 50, 50, 0, 'league'),
            (2, 2, {latest}, 5, 50, 50, 0, 'league')
    """)

    movers = archetype.load_movers_and_shakers(1, min_matches=1)

    assert [a.id for a in movers] == [1]
    assert float(movers[0].meta_share) == 1.0
    assert float(movers[0].meta_share_change) == 0.0


def test_load_archetype_finds_accented_name_spelled_without_accents() -> None:
    """/archetypes/Seance/ has always worked because the collation ignores accents. Keep it working."""
    db().execute("INSERT INTO archetype (name, description) VALUES ('Séance', '')")

    assert archetype.load_archetype(merge_slashes('Seance')).name == 'Séance'
    assert archetype.load_archetype(merge_slashes('Séance')).name == 'Séance'


@with_test_db
@pytest.mark.functional
def test_load_movers_and_shakers_includes_an_archetype_that_stopped_being_played() -> None:
    archetype.preaggregate_archetype_days()
    day = 86400
    latest = 100 * day
    db().execute(f"""
        INSERT INTO _arch_day_stats
            (archetype_id, season_id, day, num_decks, wins, losses, draws, deck_type)
        VALUES
            (1, 1, {latest - day * 10}, 5, 5, 5, 0, 'league'),
            (1, 1, {latest}, 5, 5, 5, 0, 'league'),
            -- Played a lot last week and nothing at all this week, which is the most dramatic fall
            -- there is and so must not be filtered out for having no matches in the current window.
            (2, 1, {latest - day * 10}, 5, 5, 5, 0, 'league')
    """)

    movers = archetype.load_movers_and_shakers(1, min_matches=10)

    assert [a.id for a in movers] == [1, 2]
    assert float(movers[1].meta_share) == 0.0
    assert float(movers[1].meta_share_change) == -0.5
    assert movers[1].win_percent is None


def test_load_archetype_still_finds_names_with_dashes_around_slashes() -> None:
    """-1/-1 Counters is the case #15124 did fix; do not regress it."""
    db().execute("INSERT INTO archetype (name, description) VALUES ('-1/-1 Counters', '')")

    assert archetype.load_archetype(merge_slashes('-1/-1 Counters')).name == '-1/-1 Counters'


@with_test_db
@pytest.mark.functional
def test_load_archetype_raises_for_unknown_name() -> None:
    db().execute("INSERT INTO archetype (name, description) VALUES ('Leave // Chance Midrange', '')")

    with pytest.raises(DoesNotExistException):
        archetype.load_archetype(merge_slashes('Arrive // Fortune Midrange'))
