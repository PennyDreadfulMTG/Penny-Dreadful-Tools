from decksite.view import View

class Home(View):
    def __init__(self, decks):
        self._decks = decks

    def decks(self):
        return self._decks
