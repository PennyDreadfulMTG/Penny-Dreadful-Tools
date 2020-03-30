from mypy_extensions import TypedDict

from .card_description import CardDescription

PriceDataType = TypedDict('PriceDataType', {
    'time': int,
    'low': str,
    'high': str,
    'price': str,
    'week': float,
    'month': float,
    'season': float,
})
