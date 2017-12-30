from flask import url_for

from decksite.view import View

# pylint: disable=no-self-use
class EditMatches(View):
    def __init__(self, matches):
        self.matches = matches
        for m in self.matches:
            m.left_url = url_for('deck', deck_id=m.left_id)
            if m.get('right_url'):
                m.right_url = url_for('deck', deck_id=m.right_id)
            else:
                m.right_url = None

    def subtitle(self):
        return 'Edit Matches'
