from typing import List

from flask import url_for

from decksite.view import View
from magic.models import Deck
from shared import dtutil
from shared.container import Container


# pylint: disable=no-self-use
class EditMatches(View):
    def __init__(self, decks: List[Deck], matches: List[Container]) -> None:
        super().__init__()
        self.matches = matches
        self.hide_active_runs = False
        self.decks = sorted(decks, key=lambda d: d.person + str(d.created_date))
        decks_by_id = {d.id: d for d in decks}
        for m in self.matches:
            m.display_date = dtutil.display_date(m.date)
            m.left_deck = decks_by_id.get(int(m.left_id))
            m.right_deck = decks_by_id.get(int(m.right_id))
            m.left_url = url_for('deck', deck_id=m.left_id)
            if m.get('right_id'):
                m.right_url = url_for('deck', deck_id=m.right_id)
            else:
                m.right_url = None

    def page_title(self):
        return 'Edit Matches'
