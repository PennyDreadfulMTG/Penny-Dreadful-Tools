import random

from .error import ErrorView


# pylint: disable=no-self-use
class InternalServerError(ErrorView):
    def __init__(self, exception: Exception) -> None:
        super().__init__()
        self.exception = str(exception)
        self.card = super().make_card(random.choice(['Erratic Explosion', 'Curse of Chaos', 'Anarchy']))
        self.cards = [self.card]

    def message(self):
        return 'Something went wrong.'

    def template(self):
        return 'error'

    def page_title(self):
        return 'Internal Server Error'
