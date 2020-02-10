from typing import Any, Dict, List, Sequence

from flask import url_for

from decksite.view import View
from magic import rotation
from magic.models import Card


# pylint: disable=no-self-use, too-many-arguments, too-many-instance-attributes
class RotationChanges(View):
    def __init__(self, cards_in: Sequence[Card], cards_out: Sequence[Card], playability: Dict[str, float], speculation: bool = False, query: str = '') -> None:
        super().__init__()
        self.sections: List[Dict[str, Any]] = []
        self.cards = list(cards_in) + list(cards_out)
        entries_in = [{'name': c.name, 'card': c, 'interestingness': rotation.interesting(playability, c, speculation)} for c in cards_in]
        entries_out = [{'name': c.name, 'card': c, 'interestingness': rotation.interesting(playability, c, speculation, new=False)} for c in cards_out]
        self.sections.append({'name': 'New this season', 'entries': entries_in, 'num_entries': len(entries_in)})
        self.sections.append({'name': 'Rotated out', 'entries': entries_out, 'num_entries': len(entries_out)})
        self.speculation = speculation
        self.show_interesting = True
        self.show_seasons = not speculation
        self.query = query
        self.show_interestingness_filter = True
        self.show_filters_toggle = True
        self.new_cards_deck_url = url_for('rotation_changes_files', changes_type='new')
        self.rotated_out_cards_deck_url = url_for('rotation_changes_files', changes_type='out')
        self.show_downloads = True

    def page_title(self) -> str:
        if self.speculation:
            return 'Rotation Speculation'
        return 'Rotation Changes'
