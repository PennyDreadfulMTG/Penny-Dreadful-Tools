from flask import url_for

from decksite.deck_type import DeckType
from decksite.view import View


class Cards(View):
    def __init__(self, tournament_only: bool = False) -> None:
        super().__init__()
        self.show_seasons = True
        self.show_tournament_toggle = True
        self.tournament_only = self.hide_source = tournament_only
        self.toggle_results_url = url_for('.cards', deck_type=None if tournament_only else DeckType.TOURNAMENT.value)
        self.has_cards = True

    def page_title(self) -> str:
        return 'Cards'
