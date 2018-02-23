import random

from decksite.view import View
from magic import oracle


# pylint: disable=no-self-use
class NotFound(View):
    def __init__(self, exception):
        self.exception = str(exception)
        self.card = random.choice(oracle.load_cards(where="c.name LIKE '%%Lost%%'"))
        self.cards = [self.card]

    def message(self):
        return "We couldn't find that."

    def template(self):
        return 'error'

    def subtitle(self):
        return 'Not Found'
