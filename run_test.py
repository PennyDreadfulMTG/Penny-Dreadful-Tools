import pytest
from click.testing import CliRunner

import run
from magic import multiverse, whoosh_write


def test_init_cards_force_rebuilds_search_index(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool | None]] = []

    def init(force: bool = False) -> bool:
        calls.append(('init', force))
        return True

    monkeypatch.setattr(multiverse, 'init', init)
    monkeypatch.setattr(multiverse, 'rebuild_cache', lambda: calls.append(('rebuild_cache', None)))
    monkeypatch.setattr(whoosh_write, 'reindex', lambda: calls.append(('reindex', None)))

    result = CliRunner().invoke(run.cli, ['init-cards', '--force'])

    assert result.exit_code == 0
    assert calls == [('init', True), ('reindex', None)]  # init_async's `finally` already rebuilt the cache.


def test_init_cards_does_not_rebuild_search_index_after_failed_update(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(multiverse, 'init', lambda force=False: False)
    rebuild_calls = 0

    def rebuild_cache() -> None:
        nonlocal rebuild_calls
        rebuild_calls += 1

    monkeypatch.setattr(multiverse, 'rebuild_cache', rebuild_cache)
    reindex_calls = 0

    def reindex() -> None:
        nonlocal reindex_calls
        reindex_calls += 1

    monkeypatch.setattr(whoosh_write, 'reindex', reindex)

    result = CliRunner().invoke(run.cli, ['init-cards', '--force'])

    assert result.exit_code == 1
    assert reindex_calls == 0
    assert rebuild_calls == 1  # We can't know whether init rebuilt it, and this command doubles as "regenerate my _cache_card".
