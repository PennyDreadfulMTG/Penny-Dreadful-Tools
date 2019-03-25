from typing import Any, Dict, List, Optional

from mypy_extensions import TypedDict

SetCode = str

# Type as returned by scryfall fetching
CardDescription = TypedDict('CardDescription', {
    'all_parts': Optional[List[Any]],
    'artist': str,
    'card_faces': Optional[List[Any]],
    'cmc': int,
    'collector_number': str,
    'colors': List[str],
    'color_identity': List[str],
    'flavor_text': Optional[str],
    'hand_modifier': int,
    'id': str,
    'imageName': str,
    'layout': str,
    'legalities': List[Dict[str, Any]],
    'life_modifier': int,
    'loyalty': int,
    'mana_cost': str,
    'name': str,
    'oracle_text': str,
    'power': int,
    'toughness': int,
    'reserved': bool,
    'rarity': str,
    'set': str,
    'type_line': str,
    'types': List[str],
    'watermark': Optional[str]
})
