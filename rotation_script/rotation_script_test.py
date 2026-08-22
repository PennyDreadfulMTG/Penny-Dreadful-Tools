from pathlib import Path
from types import SimpleNamespace

import pytest

from rotation_script import rotation_script
from shared import configuration
from shared.pd_exception import InvalidDataException


def test_canonical_legal_name_uses_imported_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    names = {
        'Agent Venom': 'Agent Venom',
        'Rhilex the Accursed': 'Agent Venom',
    }
    monkeypatch.setattr(rotation_script.oracle, 'valid_name', names.__getitem__)
    assert rotation_script.canonical_legal_name('Rhilex the Accursed', {}) == 'Agent Venom'

def test_canonical_legal_name_preserves_unknown_names(monkeypatch: pytest.MonkeyPatch) -> None:
    def unknown(_name: str) -> str:
        raise InvalidDataException()

    monkeypatch.setattr(rotation_script.oracle, 'valid_name', unknown)
    assert rotation_script.canonical_legal_name('A Future Card', {}) == 'A Future Card'

def test_process_writes_one_canonical_hit_for_equivalent_names(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_hits: set[str] = set()
    monkeypatch.setattr(rotation_script.oracle, 'canonical_name_or_self', lambda name: 'Agent Venom' if name == 'Rhilex the Accursed' else name)
    monkeypatch.setattr(rotation_script, 'is_good_set', lambda _set_code: True)

    def process_sets(_seen: set[str], _used: set[str], hits: set[str], _ignored: set[str]) -> int:
        captured_hits.update(hits)
        return 1

    monkeypatch.setattr(rotation_script, 'process_sets', process_sets)
    prices = {
        'prices': [
            ('Agent Venom', '0.01', 'TST'),
            ('Rhilex the Accursed', '0.01', 'TST'),
            ('A Future Card', '0.01', 'TST'),
        ],
    }

    assert rotation_script.process(prices) == 1
    assert captured_hits == {'Agent Venom', 'A Future Card'}

def test_file_sha256(tmp_path: Path) -> None:
    path = tmp_path / 'legal_cards.txt'
    path.write_text('Agent Venom\n', encoding='utf-8')

    assert rotation_script.file_sha256(str(path)) == 'fb5349f0ac8f2d4ca12c9278ebc1f5aa918b9cafbb2533a5ee3f25212d8c4c81'

def test_make_final_list_combines_equivalent_printing_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / 'Run_001.txt').write_text('Rhilex the Accursed\n', encoding='utf-8')
    (tmp_path / 'Run_002.txt').write_text('Agent Venom\n', encoding='utf-8')
    monkeypatch.setitem(configuration.CONFIG, 'legality_dir', str(tmp_path))
    monkeypatch.setattr(rotation_script.rotation, 'files', lambda: [str(tmp_path / 'Run_001.txt'), str(tmp_path / 'Run_002.txt')])
    monkeypatch.setattr(rotation_script.rotation, 'TOTAL_RUNS', 4)
    monkeypatch.setattr(rotation_script.fetcher, 'search_scryfall', lambda _query, _exhaustive: (0, [], []))
    monkeypatch.setattr(rotation_script, 'prepare_flavornames', lambda: {})
    monkeypatch.setattr(rotation_script.oracle, 'init', lambda force=False: None)
    monkeypatch.setattr(
        rotation_script.oracle,
        'valid_name',
        lambda name: 'Agent Venom' if name == 'Rhilex the Accursed' else name,
    )
    monkeypatch.setattr(rotation_script, 'is_supplemental', lambda: False)
    monkeypatch.setattr(rotation_script.seasons, 'next_rotation_ex', lambda: SimpleNamespace(mtgo_code='TST'))

    rotation_script.make_final_list()

    assert (tmp_path / 'legal_cards.txt').read_text(encoding='utf-8') == 'Agent Venom\n'
    assert (tmp_path / 'TST_legal_cards.txt').read_text(encoding='utf-8') == 'Agent Venom\n'
