from decimal import Decimal

from flask_babel import format_decimal


def display_number(value: int | float | Decimal | None, format: str | None = None) -> str:
    """Format a number for web display, using a dash for an undefined value."""
    return '—' if value is None else format_decimal(value, format=format)
