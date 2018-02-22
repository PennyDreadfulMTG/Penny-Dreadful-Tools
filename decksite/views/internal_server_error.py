import random

from decksite.view import View
from magic import oracle


# pylint: disable=no-self-use
class InternalServerError(View):
    def __init__(self, exception):
        self.exception = str(exception)
        self.card = random.choice(oracle.load_cards(['Erratic Explosion', 'Curse of Chaos', 'Anarchy']))
        self.cards = [self.card]

    def message(self):
        return 'Something went wrong.'

    def template(self):
        return 'error'

    def subtitle(self):
        return 'Internal Server Error'
