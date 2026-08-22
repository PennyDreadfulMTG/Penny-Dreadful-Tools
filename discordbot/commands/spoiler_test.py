import asyncio
import time
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from discordbot.commands import spoiler
from shared.fetch_tools import FetchException


@contextmanager
def serve_response(payload: bytes, content_type: str, delay: float = 0.15) -> Generator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            time.sleep(delay)
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/image.jpg'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def spoiler_card(image_url: str) -> dict:
    return {
        'object': 'card',
        'name': 'Unnatural Summons',
        'set': 'ydsk',
        'collector_number': '27',
        'mana_cost': '{1}{G}{U}',
        'image_uris': {'normal': image_url},
    }


@pytest.mark.asyncio
async def test_spoiler_does_not_send_invalid_image(monkeypatch: pytest.MonkeyPatch) -> None:
    card = spoiler_card('https://example.com/not-an-image.jpg')
    ctx = SimpleNamespace(
        author=SimpleNamespace(mention='<@123>'),
        bot=Mock(),
        defer=AsyncMock(),
        send=AsyncMock(),
    )
    fetch_card = AsyncMock(return_value=card)
    monkeypatch.setattr(spoiler.fetch_tools, 'fetch_json_async', fetch_card)
    download_image = AsyncMock(side_effect=FetchException('invalid image'))
    monkeypatch.setattr(spoiler.asyncio, 'to_thread', download_image)
    monkeypatch.setattr(spoiler.configuration, 'get', Mock(return_value='/tmp'))
    monkeypatch.setattr(spoiler.emoji, 'replace_emoji', AsyncMock(return_value='Unnatural Summons 1GU'))
    import_card = AsyncMock()
    monkeypatch.setattr(spoiler.oracle, 'scryfall_import_async', import_card)

    await spoiler.Spoiler.spoiler.callback(SimpleNamespace(), ctx, 'Unnatural Summons')

    ctx.defer.assert_awaited_once_with()
    fetch_card.assert_awaited_once_with('https://api.scryfall.com/cards/named?fuzzy=Unnatural Summons')
    download_image.assert_awaited_once_with(spoiler.fetch_tools.store_image, 'https://example.com/not-an-image.jpg', '/tmp/ydsk_27.jpg')
    ctx.send.assert_awaited_once_with(content='Unnatural Summons 1GU\nImage unavailable.')
    import_card.assert_awaited_once_with('Unnatural Summons')


@pytest.mark.asyncio
async def test_spoiler_keeps_event_loop_responsive_during_real_image_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image = Path('discordbot/commands/img/mana-frank.png').read_bytes()
    with serve_response(image, 'image/png') as image_url:
        card = spoiler_card(image_url)
        ctx = SimpleNamespace(
            author=SimpleNamespace(mention='<@123>'),
            bot=Mock(guilds=[]),
            defer=AsyncMock(),
            send=AsyncMock(),
        )
        monkeypatch.setattr(spoiler.fetch_tools, 'fetch_json_async', AsyncMock(return_value=card))
        monkeypatch.setattr(spoiler.configuration, 'get', Mock(return_value=str(tmp_path)))
        monkeypatch.setattr(spoiler.emoji, 'replace_emoji', AsyncMock(return_value='Unnatural Summons 1GU'))
        monkeypatch.setattr(spoiler.oracle, 'scryfall_import_async', AsyncMock())

        task = asyncio.create_task(spoiler.Spoiler.spoiler.callback(SimpleNamespace(), ctx, 'Unnatural Summons'))
        ticks = 0
        while not task.done():
            ticks += 1
            await asyncio.sleep(0.01)
        await task

    assert ticks >= 5
    ctx.defer.assert_awaited_once_with()
    assert (tmp_path / 'ydsk_27.jpg').is_file()
    assert 'file' in ctx.send.await_args.kwargs


@pytest.mark.asyncio
async def test_spoiler_rejects_real_non_image_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with serve_response(b'<html>This is not an image.</html>', 'text/html', delay=0) as image_url:
        card = spoiler_card(image_url)
        ctx = SimpleNamespace(
            author=SimpleNamespace(mention='<@123>'),
            bot=Mock(guilds=[]),
            defer=AsyncMock(),
            send=AsyncMock(),
        )
        monkeypatch.setattr(spoiler.fetch_tools, 'fetch_json_async', AsyncMock(return_value=card))
        monkeypatch.setattr(spoiler.configuration, 'get', Mock(return_value=str(tmp_path)))
        monkeypatch.setattr(spoiler.emoji, 'replace_emoji', AsyncMock(return_value='Unnatural Summons 1GU'))
        monkeypatch.setattr(spoiler.oracle, 'scryfall_import_async', AsyncMock())

        await spoiler.Spoiler.spoiler.callback(SimpleNamespace(), ctx, 'Unnatural Summons')

    assert not (tmp_path / 'ydsk_27.jpg').exists()
    ctx.send.assert_awaited_once_with(content='Unnatural Summons 1GU\nImage unavailable.')


@pytest.mark.asyncio
async def test_async_fetch_keeps_event_loop_responsive_during_real_http_delay() -> None:
    with serve_response(b'{"ok": true}', 'application/json') as url:
        task = asyncio.create_task(spoiler.fetch_tools.fetch_json_async(url))
        ticks = 0
        while not task.done():
            ticks += 1
            await asyncio.sleep(0.01)
        result = await task

    assert result == {'ok': True}
    assert ticks >= 5
