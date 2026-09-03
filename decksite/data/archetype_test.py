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


def _make_hierarchy() -> None:
    """Aggro (root) with child Red Deck Wins, and Control (root) with no children. Decks belong only to the leaves."""
    db().execute("DELETE FROM archetype_closure")
    db().execute("DELETE FROM archetype")
    db().execute("INSERT INTO archetype (id, name, description) VALUES (1, 'Aggro', ''), (2, 'Red Deck Wins', ''), (3, 'Control', '')")
    db().execute("""
        INSERT INTO archetype_closure (ancestor, descendant, depth) VALUES
            (1, 1, 0), (2, 2, 0), (3, 3, 0),
            (1, 2, 1)
    """)


@with_test_db
@pytest.mark.functional
def test_home_page_archetypes_do_not_roll_children_into_parents() -> None:
    """#15109 used load_archetypes, whose parents absorb their children, so the home page listed only taxonomy roots."""
    _make_hierarchy()
    archetype.preaggregate_disjoint_archetypes()
    archetype.preaggregate_archetypes()
    for table in ('_arch_disjoint_stats', '_arch_stats'):
        db().execute(f"""
            INSERT INTO {table}
                (archetype_id, season_id, num_decks, wins, losses, draws, perfect_runs, tournament_wins, tournament_top8s, deck_type)
            VALUES
                (2, 1, 10, 0, 0, 0, 0, 0, 0, 'league'),
                (3, 1, 4, 0, 0, 0, 0, 0, 0, 'league')
        """)
    # _arch_stats is the inclusive table, so Aggro carries Red Deck Wins' decks there but not in the disjoint one.
    db().execute("""
        INSERT INTO _arch_stats
            (archetype_id, season_id, num_decks, wins, losses, draws, perfect_runs, tournament_wins, tournament_top8s, deck_type)
        VALUES (1, 1, 10, 0, 0, 0, 0, 0, 0, 'league')
    """)

    disjoint, _ = archetype.load_disjoint_archetypes(order_by='num_decks DESC', season_id=1)
    by_name = {a.name: a.num_decks for a in disjoint if a.get('num_decks')}

    assert by_name == {'Red Deck Wins': 10, 'Control': 4}, 'the home page must show the archetypes decks are actually assigned to'
    assert 'Aggro' not in by_name, 'Aggro has no decks of its own; it only looks popular when children are rolled up'


@with_test_db
@pytest.mark.functional
def test_home_page_archetype_counts_add_up_to_the_number_of_decks() -> None:
    """The property that makes the list a metagame breakdown: each deck counted once.

    A parent may legitimately appear next to its child if it has decks of its own, but its count must
    exclude the child's. Under the inclusive loader Aggro would read 11 and the column would sum to 25.
    """
    _make_hierarchy()
    archetype.preaggregate_disjoint_archetypes()
    db().execute("""
        INSERT INTO _arch_disjoint_stats
            (archetype_id, season_id, num_decks, wins, losses, draws, perfect_runs, tournament_wins, tournament_top8s, deck_type)
        VALUES
            (1, 1, 1, 0, 0, 0, 0, 0, 0, 'league'),
            (2, 1, 10, 0, 0, 0, 0, 0, 0, 'league'),
            (3, 1, 4, 0, 0, 0, 0, 0, 0, 'league')
    """)

    shown, _ = archetype.load_disjoint_archetypes(order_by='num_decks DESC', season_id=1)
    shown = [a for a in shown if a.get('num_decks')][:8]  # What Home.setup_archetypes does.
    counts = {a.name: a.num_decks for a in shown}

    assert counts == {'Red Deck Wins': 10, 'Control': 4, 'Aggro': 1}
    assert sum(counts.values()) == 15, 'the counts must add up to the number of decks, not more'
