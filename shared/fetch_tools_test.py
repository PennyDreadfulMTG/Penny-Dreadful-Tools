import gzip
import io
import json
from pathlib import Path
from unittest.mock import Mock, patch

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
