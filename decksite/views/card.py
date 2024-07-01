from typing import Any

from flask import url_for

from decksite.deck_type import DeckType
from decksite.view import View
from magic import seasons
from magic.models import Card as CardContainer


class Card(View):
    def __init__(self, card: CardContainer, tournament_only: bool = False) -> None:
        super().__init__()
        self.legal_formats = [x for x, y in card.legalities.items() if y == 'Legal'] + [x + ' (restricted)' for x, y in card.legalities.items() if y == 'Restricted']
        self.legal_seasons = sorted(seasons.SEASONS.index(fmt.replace('Penny Dreadful ', '')) + 1 for fmt, v in card.legalities.items() if 'Penny Dreadful' in fmt and v != 'Banned')
        self.show_seasons = True
        self.show_archetype = True
        self.show_tournament_toggle = True
        self.tournament_only = self.hide_source = tournament_only
        self.public = True  # Mark this as 'public' so it can share legality section code with deck.
        self.toggle_results_url = url_for('.card', name=card.name, deck_type=None if tournament_only else DeckType.TOURNAMENT.value)
        self.card = card
        self.cards = [self.card]

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.card, attr)

    def page_title(self) -> str:
        return self.card.name
