from typing import Any

from flask import url_for

from decksite.view import View
from magic.models import Card as CardContainer


# pylint: disable=no-self-use, too-many-instance-attributes
class Card(View):
    def __init__(self, card: CardContainer, tournament_only: bool = False) -> None:
        super().__init__()
        self.decks = card.decks
        self.legal_formats = ([x for x, y in card.legalities.items() if y == 'Legal'] +
                              [x + ' (restricted)' for x, y in card.legalities.items() if y == 'Restricted'])
        self.show_seasons = True
        self.show_archetype = True
        self.show_tournament_toggle = True
        self.tournament_only = self.hide_source = tournament_only
        self.public = True # Mark this as 'public' so it can share legality section code with deck.

        if tournament_only:
            self.toggle_results_url = url_for('.card', name=card.name)
        else:
            self.toggle_results_url = url_for('.card_tournament', name=card.name)

        self.card = card
        if tournament_only:
            self.card.num_decks = card.num_decks_tournament
            self.card.win_percent = card.win_percent_tournament
            self.card.wins = card.wins_tournament
            self.card.losses = card.losses_tournament
            self.card.draws = card.draws_tournament

        self.cards = [self.card]

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.card, attr)

    def page_title(self):
        return self.card.name
