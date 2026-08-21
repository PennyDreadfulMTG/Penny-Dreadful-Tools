import gzip
import io
import json

from shared import fetch_tools


def test_load_jsonl_gzip() -> None:
    rows = [{'name': 'Forest'}, {'name': 'Island'}]
    contents = gzip.compress(b''.join(f'{json.dumps(row)}\n'.encode() for row in rows))

    assert fetch_tools.load_jsonl_gzip(io.BytesIO(contents)) == rows
