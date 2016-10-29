from decksite.view import View

# pylint: disable=no-self-use
class Home(View):
    def __init__(self, decks):
        self._decks = decks
        for d in self._decks:
            if d.finish == 1:
                d.top8 = '①'
            elif d.finish == 2:
                d.top8 = '②'
            elif d.finish == 3:
                d.top8 = '④'
            elif d.finish == 5:
                d.top8 = '⑧'
            else:
                d.top8 = ''

    def decks(self):
        return self._decks

    def subtitle(self):
        return None
