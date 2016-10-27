from decksite.view import View

# pylint: disable=no-self-use
class Home(View):
    def __init__(self, decks):
        self._decks = decks

    def decks(self):
        return self._decks

    def subtitle(self):
        return None

    def title(self):
        if not self.subtitle():
            return 'Penny Dreadful Decks'
        else:
            return '{subtitle} – Penny Dreadful Decks'.format(subtitle=self.subtitle())
