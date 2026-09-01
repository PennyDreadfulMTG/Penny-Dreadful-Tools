from decimal import Decimal
from typing import Any
from unittest import mock

import pytest

from decksite.data import archetype


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
