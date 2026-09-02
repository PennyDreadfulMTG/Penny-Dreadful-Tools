from decimal import Decimal
from typing import Any
from unittest import mock

import pytest

from decksite.data import archetype, clauses
from decksite.database import db
from decksite.testutil import with_test_db


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
