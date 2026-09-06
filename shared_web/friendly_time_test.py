import datetime
import re
from pathlib import Path

import pytest

from decksite.main import APP
from shared import dtutil
from shared_web import friendly_time, template


def test_friendly_date_keeps_relative_text_and_exact_datetime(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.datetime(2026, 9, 6, 12, tzinfo=datetime.UTC)
    then = now - datetime.timedelta(days=3, hours=2)
    monkeypatch.setattr(dtutil, 'now', lambda tz=None: now if tz is None else now.astimezone(tz))

    date = friendly_time.friendly_date(then)

    assert date.display == '3 days ago'
    assert date.datetime == '2026-09-03T10:00:00+00:00'


def test_friendly_time_partial_uses_semantic_time_markup() -> None:
    with APP.test_request_context('/'):
        html = template.render_name('friendlytime', {'display': '3 days ago', 'datetime': '2026-09-03T10:00:00+00:00'})

    assert html.strip() == '<time datetime="2026-09-03T10:00:00+00:00">3 days ago</time>'


def test_web_dates_use_shared_friendly_time_rendering() -> None:
    direct_calls = []
    for root in ('decksite', 'logsite'):
        for path in Path(root).rglob('*.py'):
            if path.name.endswith('_test.py') or path == Path('decksite/league.py'):
                continue
            for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if 'dtutil.display_date(' in line:
                    direct_calls.append(f'{path}:{line_number}')
    assert direct_calls == [], f'Web dates must use shared_web.friendly_time, not dtutil.display_date directly: {direct_calls}'

    legacy_fields = re.compile(r'{{{?\s*(display_date|display_last_sorted|season_(start|end)_display|start_date_display|end_date_display)\b')
    raw_template_fields = []
    for root in ('decksite/templates', 'logsite/templates'):
        for path in Path(root).glob('*.mustache'):
            if legacy_fields.search(path.read_text(encoding='utf-8')):
                raw_template_fields.append(str(path))
    assert raw_template_fields == [], f'Web dates must use the friendlytime partial: {raw_template_fields}'
