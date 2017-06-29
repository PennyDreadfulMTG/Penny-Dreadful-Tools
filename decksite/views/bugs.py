from magic import oracle
from decksite.view import View

# pylint: disable=no-self-use
class Bugs(View):
    def __init__(self):
        self.cards = oracle.bugged_cards()

    def subtitle(self):
        return 'Bugged Cards'
