from decksite.view import View

# pylint: disable=no-self-use
class Home(View):
    def __init__(self, decks):
        self._decks = decks

    def decks(self):
        return self._decks

    def subtitle(self):
        return None
