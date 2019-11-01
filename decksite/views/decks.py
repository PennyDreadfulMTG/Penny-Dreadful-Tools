from typing import Union

from decksite.view import View


# pylint: disable=no-self-use
class Decks(View):
    def __init__(self) -> None:
        super().__init__()
        self.show_seasons = True

    def page_title(self):
        return '{season_name} Decks'.format(season_name=self.season_name())
