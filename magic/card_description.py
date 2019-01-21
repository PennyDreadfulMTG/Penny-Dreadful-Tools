from typing import Any, Dict, List, Optional

from mypy_extensions import TypedDict

SetCode = str
CardDescription = TypedDict('CardDescription', {
    'all_parts': Optional[List[Any]],
    'card_faces': Optional[List[Any]],
    'cmc': int,
    'imageName': str,
    'layout': str,
    'legalities': List[Dict[str, Any]],
    'manaCost': str,
    'name': str,
    'oracle_text': str,
    'rarity': str,
    'set': str,
    'type_line': str,
    'types': List[str]
})
