from decksite.view import View

# pylint: disable=no-self-use
class Home(View):
    def __init__(self, decks):
        self.decks = decks

    def subtitle(self):
        return None
