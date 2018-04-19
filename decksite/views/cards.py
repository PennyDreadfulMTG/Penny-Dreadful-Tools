from decksite.view import View


# pylint: disable=no-self-use
class Cards(View):
    def __init__(self, cards):
        super().__init__()
        self.cards = cards

    def page_title(self):
        return 'Cards'
