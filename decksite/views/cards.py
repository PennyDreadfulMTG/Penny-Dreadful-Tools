from typing import List

from flask import url_for

from decksite.deck_type import DeckType
from decksite.view import View
from magic.models import Card
from magic.rotation import current_season_num


# pylint: disable=no-self-use, too-many-instance-attributes
class Cards(View):
    def __init__(self, cards: List[Card], tournament_only: bool = False, query: str = '') -> None:
        super().__init__()
        self.show_seasons = True
        self.show_tournament_toggle = True
        self.tournament_only = self.hide_source = tournament_only
        self.query = query
        self.toggle_results_url = url_for('.cards', deck_type=None if tournament_only else DeckType.TOURNAMENT.value)
        self.cards = cards

    def page_title(self) -> str:
        return 'Cards'
