from typing import Any

from decksite.view import View
from magic.models import Card as CardContainer


# pylint: disable=no-self-use
class Card(View):
    def __init__(self, card: CardContainer) -> None:
        super().__init__()
        self.card = card
        self.cards = [card]
        self.decks = card.decks
        self.legal_formats = card.legalities.keys()
        self.show_seasons = True
        self.show_archetype = True

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.card, attr)

    def page_title(self):
        return self.card.name
