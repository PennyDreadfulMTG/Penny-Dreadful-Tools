from typing import List

from flask import url_for

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
        # if it's the current season, allow the scryfall filter to add "f:pd" to speed up results
        if self.season_id() == current_season_num():
            self.filter_current_season = True
        self.toggle_results_url = url_for('.cards', deck_type=None if tournament_only else 'tournament')
        self.cards = cards
        self.show_filters_toggle = True

    def page_title(self) -> str:
        return 'Cards'
