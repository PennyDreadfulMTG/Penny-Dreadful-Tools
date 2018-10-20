from flask import url_for

from decksite.data import deck
from decksite.view import View
from shared import dtutil


# pylint: disable=no-self-use
class EditMatches(View):
    def __init__(self, matches) -> None:
        super().__init__()
        self.matches = matches
        if matches:
            deck_ids = [m.left_id for m in self.matches] + [m.right_id for m in self.matches if m.right_id is not None]
            decks_by_id = {int(d.id): d for d in deck.load_decks('d.id IN ({deck_ids})'.format(deck_ids=', '.join(deck_ids)))}
            self.decks = sorted(decks_by_id.values(), key=lambda d: d.person + d.name + str(d.created_date))
            for m in self.matches:
                m.display_date = dtutil.display_date(m.date)
                m.left_deck = decks_by_id.get(int(m.left_id))
                m.right_deck = decks_by_id.get(int(m.right_id))
                m.left_url = url_for('deck', deck_id=m.left_id)
                if m.get('right_url'):
                    m.right_url = url_for('deck', deck_id=m.right_id)
                else:
                    m.right_url = None

    def page_title(self):
        return 'Edit Matches'
