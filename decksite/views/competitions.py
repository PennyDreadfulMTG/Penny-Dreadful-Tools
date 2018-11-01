from typing import List

from decksite.data.competition import Competition
from decksite.view import View


# pylint: disable=no-self-use
class Competitions(View):
    def __init__(self, competitions: List[Competition]) -> None:
        super().__init__()
        self.competitions = competitions
        self.show_seasons = True

    def page_title(self):
        return 'Competitions'
