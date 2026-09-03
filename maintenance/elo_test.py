from typing import Any

import pytest

from maintenance import elo
from shared.container import Container


def test_run_reads_people_as_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """person.load_people returns a list, not (list, total). Unpacking it crashed the daily job."""
    updates: list[list[Any]] = []

    class FakeDb:
        def select(self, sql: str) -> list[dict[str, str]]:
            return [{'people': '1,2', 'games': '2,0'}]

        def execute(self, sql: str, args: list[Any]) -> int:
            updates.append(args)
            return 1

    monkeypatch.setattr(elo, 'db', lambda: FakeDb())
    monkeypatch.setattr(elo.person, 'load_people', lambda: [Container({'id': 1, 'elo': 1500}), Container({'id': 2, 'elo': 1500})])
    monkeypatch.setattr(elo, 'PEOPLE', {})

    elo.run()

    assert len(updates) == 2
    assert {person_id for _, person_id in updates} == {1, 2}
