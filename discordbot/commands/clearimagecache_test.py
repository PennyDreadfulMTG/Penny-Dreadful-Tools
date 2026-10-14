from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from discordbot.commands import clearimagecache


@pytest.mark.asyncio
async def test_clear_image_cache_removes_jpeg_and_webp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for filename in ['card.jpg', 'card.webp', 'card.art_crop_small.webp', 'banner.png']:
        (tmp_path / filename).touch()
    monkeypatch.setattr(clearimagecache.configuration, 'get', lambda _key: str(tmp_path))
    ctx = SimpleNamespace(send=AsyncMock())

    await clearimagecache.ClearImageCache.clearimagecache.callback(SimpleNamespace(), ctx)

    assert sorted(path.name for path in tmp_path.iterdir()) == ['banner.png']
    ctx.send.assert_awaited_once_with('3 cleared.')
