from pathlib import Path
from typing import Any

import pytest

from decksite.data import rotation as rotation_data


class FakeDatabase:
    def __init__(self) -> None:
        self.sql = ''

    def execute(self, sql: str, _args: list[Any] | None = None) -> int:
        self.sql = sql
        return 1


def test_update_rotation_runs_stores_canonical_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'Run_001.txt'
    path.write_text('Agent Venom\nRhilex the Accursed\nA Future Card\n', encoding='utf-8')
    database = FakeDatabase()
    monkeypatch.setattr(rotation_data, 'db', lambda: database)
    monkeypatch.setattr(rotation_data.rotation, 'files', lambda: [str(path)])
    monkeypatch.setattr(rotation_data.seasons, 'next_season_num', lambda: 99)
    monkeypatch.setattr(rotation_data.oracle, 'canonical_name_or_self', lambda name: 'Agent Venom' if name == 'Rhilex the Accursed' else name)

    rotation_data.update_rotation_runs()

    assert database.sql.count("'Agent Venom'") == 2
    assert 'Rhilex the Accursed' not in database.sql
    assert "'A Future Card'" in database.sql
