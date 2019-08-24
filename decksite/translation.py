from typing import Dict, Optional

from decksite.data.deck import RawDeckDescription

TAPPEDOUT = {
    'date_updated': 'created_date', # We'll store this the first time as the closest appromxiation we have to the created date.
    'user': 'tappedout_username',
}

def translate(mappings: Dict[str, str], data: RawDeckDescription) -> RawDeckDescription:
    result = data.copy() # type: ignore
    for k, v in data.items():
        our_key: Optional[str] = mappings.get(k)
        if our_key is not None:
            result[our_key] = v # type: ignore
    return result
