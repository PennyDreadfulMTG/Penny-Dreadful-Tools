import gzip
import io
import json
from unittest.mock import Mock, patch

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
