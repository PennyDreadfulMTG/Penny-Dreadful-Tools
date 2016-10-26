from decksite.view import View

class Home(View):
    def __init__(self, decks):
        self.decks = decks

    def decks(self):
        return self.decks
