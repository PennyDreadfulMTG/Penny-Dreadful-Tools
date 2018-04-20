from flask import g, url_for

from decksite.view import View
from magic import rotation


# pylint: disable=no-self-use
class Decks(View):
    def __init__(self, decks):
        super().__init__()
        self.decks = decks
        self.season_url = url_for('seasons.season', season_id=g.get('season_id', rotation.current_season_num()))

    def page_title(self):
        return 'Latest Decks'
