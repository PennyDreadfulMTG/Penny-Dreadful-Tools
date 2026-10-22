from decimal import Decimal

import pytest

from decksite.main import APP
from shared_web.number import display_number


@pytest.mark.parametrize(('value', 'expected'), [
    (None, '—'),
    (0, '0.0'),
    (0.0, '0.0'),
    (Decimal('53.1'), '53.1'),
    (53.1, '53.1'),
])
def test_display_number(value: int | float | Decimal | None, expected: str) -> None:
    with APP.test_request_context('/'):
        assert display_number(value, format='#,##0.0') == expected
