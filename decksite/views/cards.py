from typing import List

from decksite.view import View
from magic.models import Card


# pylint: disable=no-self-use
class Cards(View):
    def __init__(self, cards: List[Card]) -> None:
        super().__init__()
        self.cards = cards
        self.show_seasons = True

    def page_title(self):
        return 'Cards'
