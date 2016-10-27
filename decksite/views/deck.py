from decksite.view import View

# pylint: disable=no-self-use
class Deck(View):
    def __init__(self, deck):
        self._deck = deck

    def deck(self):
        return self._deck

    def subtitle(self):
        return self._deck['name']
