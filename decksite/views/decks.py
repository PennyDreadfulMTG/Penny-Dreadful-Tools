from flask import url_for
from flask_babel import ngettext

from decksite.view import View
from magic import rotation


# pylint: disable=no-self-use
class Decks(View):
    def __init__(self, decks):
        self.decks = decks
        self.season_url = url_for('season', season_id=rotation.last_rotation_ex()['code'])
        super().__init__()

    def subtitle(self):
        return 'Latest Decks'
