from decksite.view import View
from magic import legality


# pylint: disable=no-self-use
class Card(View):
    def __init__(self, card):
        self.card = card
        self.cards = [card]
        self.decks = [d for d in card.decks if not d.is_in_current_run()]
        self.legal_formats = list(sorted(card.legalities.keys(), key=legality.order_score))

    def __getattr__(self, attr):
        return getattr(self.card, attr)

    def subtitle(self):
        return self.card.name
