from typing import List

from flask import url_for

from decksite.view import View
from magic.models import Card
from magic.rotation import current_season_num
from shared.container import Container


# pylint: disable=no-self-use
class Cards(View):
    def __init__(self, cards: List[Card], tournament_only: bool = False, query: str = '') -> None:
        super().__init__()
        self.show_seasons = True
        self.show_tournament_toggle = True
        self.tournament_only = tournament_only
        self.query = query

        # if it's the current season, allow the scryfall filter to add "f:pd" to speed up results
        if self.season_id() == current_season_num():
            self.filter_current_season = True

        if tournament_only:
            self.toggle_results_url = url_for('.cards')
        else:
            self.toggle_results_url = url_for('.cards_tournament')

        def convert(c: Container) -> Container:
            if tournament_only:
                c.num_decks = c.num_decks_tournament
                c.win_percent = c.win_percent_tournament
                c.wins = c.wins_tournament
                c.losses = c.losses_tournament
                c.draws = c.draws_tournament
            return c

        self.cards = [convert(c) for c in cards]
        self.show_filters_toggle = True

    def page_title(self):
        return 'Cards'
