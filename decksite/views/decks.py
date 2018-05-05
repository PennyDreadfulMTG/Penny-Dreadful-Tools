from flask import url_for

from decksite import get_season_id
from decksite.view import View


# pylint: disable=no-self-use
class Decks(View):
    def __init__(self, decks) -> None:
        super().__init__()
        self.decks = decks
        self.season_url = url_for('seasons.season', season_id=get_season_id())
        self.show_seasons = True

    def page_title(self):
        return '{season_name} Decks'.format(season_name=self.season_name())
