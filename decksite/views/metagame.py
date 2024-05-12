from flask import url_for

from decksite.deck_type import DeckType
from decksite.view import View


class Metagame(View):
    def __init__(self, tournament_only: bool) -> None:
        super().__init__()
        self.show_seasons = True
        self.show_tournament_toggle = True
        self.tournament_only = tournament_only
        self.has_cards = True
        self.toggle_results_url = url_for('.metagame', deck_type=None if tournament_only else DeckType.TOURNAMENT.value)

    def page_title(self) -> str:
        return 'Metagame'
