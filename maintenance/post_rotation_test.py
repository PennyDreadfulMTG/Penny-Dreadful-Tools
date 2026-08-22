import datetime
from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from maintenance import post_rotation


class EventLoop:
    def run_until_complete(self, coroutine: Coroutine[Any, Any, None]) -> None:
        coroutine.close()


def test_populates_legal_cards_after_rebuilding_card_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def record(name: str) -> Callable[[], None]:
        return lambda: calls.append(name)

    async def noop_async() -> None:
        pass

    monkeypatch.setattr(post_rotation.asyncio, 'get_event_loop', EventLoop)
    monkeypatch.setattr(post_rotation.league, 'set_status', lambda status: None)
    monkeypatch.setattr(post_rotation.league, 'active_league', lambda: type('League', (), {'end_date': datetime.datetime.min.replace(tzinfo=datetime.UTC)})())
    monkeypatch.setattr(post_rotation.multiverse, 'init', lambda: None)
    monkeypatch.setattr(post_rotation.multiverse, 'set_legal_cards_async', noop_async)
    monkeypatch.setattr(post_rotation.multiverse, 'update_pd_legality_async', noop_async)
    monkeypatch.setattr(post_rotation.insert_seasons, 'run', record('insert seasons'))
    monkeypatch.setattr(post_rotation.multiverse, 'rebuild_cache', record('rebuild card cache'))
    monkeypatch.setattr(post_rotation.playability, 'preaggregate_legal_cards', record('populate legal cards'))
    monkeypatch.setattr(post_rotation.dtutil, 'now', lambda: datetime.datetime.now(datetime.UTC))
    monkeypatch.setattr(post_rotation.redis, 'REDIS', None)

    post_rotation.ad_hoc()

    assert calls == ['insert seasons', 'rebuild card cache', 'populate legal cards']
