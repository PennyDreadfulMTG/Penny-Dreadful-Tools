from decksite.view import View


# pylint: disable=no-self-use
class Cards(View):
    def __init__(self, cards) -> None:
        super().__init__()
        self.cards = cards
        self.show_seasons = True

    def page_title(self):
        return 'Cards'
