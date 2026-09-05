import gzip
import io
import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import requests
from PIL import Image

from shared import fetch_tools


def test_fetch_sets_user_agent() -> None:
    response = Mock(status_code=200, text='ok')
    with patch.object(fetch_tools.requests, 'get', return_value=response) as get:
        assert fetch_tools.fetch('https://example.com') == 'ok'

    get.assert_called_once_with('https://example.com', headers={'User-Agent': fetch_tools.USER_AGENT})


def test_load_jsonl_gzip() -> None:
    rows = [{'name': 'Forest'}, {'name': 'Island'}]
    contents = gzip.compress(b''.join(f'{json.dumps(row)}\n'.encode() for row in rows))

    assert fetch_tools.load_jsonl_gzip(io.BytesIO(contents)) == rows


def test_store_image_rejects_non_image_response(tmp_path: Path) -> None:
    response = Mock(status_code=200, headers={'Content-Type': 'text/html'})
    destination = tmp_path / 'card.jpg'

    with patch.object(fetch_tools.requests, 'get', return_value=response), pytest.raises(fetch_tools.FetchException, match='Expected an image'):
        fetch_tools.store_image('https://example.com/card.jpg', str(destination))

    assert not destination.exists()


def test_store_image_rejects_http_error(tmp_path: Path) -> None:
    response = Mock(headers={'Content-Type': 'image/jpeg'})
    response.raise_for_status.side_effect = requests.HTTPError('404 Client Error')
    destination = tmp_path / 'card.jpg'

    with patch.object(fetch_tools.requests, 'get', return_value=response), pytest.raises(fetch_tools.FetchException, match='Could not download'):
        fetch_tools.store_image('https://example.com/card.jpg', str(destination))

    assert not destination.exists()


def test_store_image_only_publishes_valid_image(tmp_path: Path) -> None:
    contents = io.BytesIO()
    Image.new('RGB', (100, 100)).save(contents, format='BMP')
    response = Mock(headers={'Content-Type': 'image/bmp'})
    response.iter_content.return_value = [contents.getvalue()]
    destination = tmp_path / 'card.bmp'

    with patch.object(fetch_tools.requests, 'get', return_value=response):
        fetch_tools.store_image('https://example.com/card.bmp', str(destination))

    assert destination.read_bytes() == contents.getvalue()


def mock_async_response(monkeypatch: pytest.MonkeyPatch, response: Mock) -> Mock:
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.get = AsyncMock(return_value=response)
    client_session = Mock(return_value=session)
    monkeypatch.setattr(fetch_tools.aiohttp, 'ClientSession', client_session)
    return client_session


@pytest.mark.asyncio
async def test_store_async_rejects_http_error_without_replacing_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock(status=429, headers={'Content-Type': 'application/json'})
    client_session = mock_async_response(monkeypatch, response)
    destination = tmp_path / 'card.jpg'
    destination.write_bytes(b'existing image')

    with pytest.raises(fetch_tools.FetchException, match='429'):
        await fetch_tools.store_async('https://api.scryfall.com/cards/id?format=image', str(destination))

    assert destination.read_bytes() == b'existing image'
    client_session.assert_called_once_with(headers={
        'User-Agent': fetch_tools.USER_AGENT,
        'Accept': 'application/json',
    })


@pytest.mark.asyncio
async def test_store_async_rejects_non_image_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock(status=200, headers={'Content-Type': 'text/html; charset=utf-8'})
    mock_async_response(monkeypatch, response)
    destination = tmp_path / 'card.jpg'

    with pytest.raises(fetch_tools.FetchException, match='Expected an image'):
        await fetch_tools.store_async('https://cards.scryfall.io/card.jpg', str(destination))

    assert not destination.exists()


@pytest.mark.asyncio
async def test_store_async_only_publishes_a_valid_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    contents = io.BytesIO()
    Image.new('RGB', (100, 100)).save(contents, format='BMP')

    async def chunks(_size: int) -> AsyncIterator[bytes]:
        yield contents.getvalue()

    content = Mock()
    content.iter_chunked = chunks
    response = Mock(status=200, headers={'Content-Type': 'image/bmp'}, content=content)
    client_session = mock_async_response(monkeypatch, response)
    destination = tmp_path / 'card.bmp'

    await fetch_tools.store_async('https://cards.scryfall.io/card.bmp', str(destination))

    assert destination.read_bytes() == contents.getvalue()
    client_session.assert_called_once_with(headers={'User-Agent': fetch_tools.USER_AGENT})
