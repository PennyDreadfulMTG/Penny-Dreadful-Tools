from decksite.view import View


# pylint: disable=no-self-use
class Cards(View):
    def __init__(self, cards):
        self.cards = cards

    def subtitle(self):
        return 'Cards'
