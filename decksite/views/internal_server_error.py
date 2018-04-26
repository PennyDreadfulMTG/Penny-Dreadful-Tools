import random

from decksite.view import View
from magic import oracle


# pylint: disable=no-self-use
class InternalServerError(View):
    def __init__(self, exception) -> None:
        super().__init__()
        self.exception = str(exception)
        self.card = random.choice(oracle.load_cards(['Erratic Explosion', 'Curse of Chaos', 'Anarchy']))
        self.cards = [self.card]

    def message(self):
        return 'Something went wrong.'

    def template(self):
        return 'error'

    def page_title(self):
        return 'Internal Server Error'
