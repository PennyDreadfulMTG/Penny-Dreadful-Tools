from typing import List, Optional, Union

from flask import url_for

from decksite import get_season_id
from decksite.data.deck import Deck
from decksite.view import View


# pylint: disable=no-self-use
class Decks(View):
    def __init__(self, season_id: Union[int, str]) -> None:
        super().__init__()
        self.season_id = season_id
        self.show_seasons = True

    def page_title(self):
        return '{season_name} Decks'.format(season_name=self.season_name())
