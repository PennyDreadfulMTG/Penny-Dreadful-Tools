from typing import Any, Dict, List

from mypy_extensions import TypedDict

SetCode = str
CardDescription = TypedDict('CardDescription', {
    'cmc': int,
    'imageName': str,
    'layout': str,
    'manaCost': str,
    'legalities': List[Dict[str, Any]],
    'name': str,
    'printings': List[SetCode],
    'rarity': str,
    'oracle_text': str,
    'type_line': str,
    'types': List[str]
})
