from flask import url_for

from decksite.view import View

# pylint: disable=no-self-use
class Cards(View):
    def __init__(self, cards):
        self.cards = cards
        for c in self.cards:
            c.url = url_for('card', name=c.name)

    def subtitle(self):
        return 'Cards'
