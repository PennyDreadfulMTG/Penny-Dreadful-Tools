from typing import List, Optional

from flask import url_for

from decksite.view import View
from magic.models import Card
from shared.container import Container


# pylint: disable=no-self-use
class Cards(View):
    def __init__(self, cards: List[Card], tournament_only: Optional[bool] = False, only_these: Optional[List[str]] = None, query: str = '') -> None:
        super().__init__()
        self.show_seasons = True
        self.show_tournament_toggle = True
        self.tournament_only = tournament_only
        self.query = query

        self.cards = cards

        if tournament_only:
            self.toggle_results_url = url_for('.cards')
        else:
            self.toggle_results_url = url_for('.cards_tournament')

        if only_these:
            self.cards = [c for c in self.cards if c.name in only_these]

        def convert(c: Container) -> Container:
            if tournament_only:
                c.num_decks = c.num_decks_tournament
                c.win_percent = c.win_percent_tournament
                c.wins = c.wins_tournament
                c.losses = c.losses_tournament
                c.draws = c.draws_tournament
            return c

        self.cards = [convert(c) for c in self.cards]

    def page_title(self):
        return 'Cards'
