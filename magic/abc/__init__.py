from typing import TypedDict

from .card_description import CardDescription

__all__ = ['CardDescription', 'PriceDataType']

class PriceDataType(TypedDict):
    time: int
    low: str
    high: str
    price: str
    week: float
    month: float
    season: float
