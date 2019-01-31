import random

from .error import ErrorView


# pylint: disable=no-self-use
class InternalServerError(ErrorView):
    def __init__(self, exception: Exception) -> None:
        super().__init__()
        self.exception = str(exception)
        self.card = super().make_card(random.choice(['Erratic Explosion', 'Curse of Chaos', 'Anarchy', 'Pandemonium', 'Widespread Panic']))
        self.cards = [self.card]

    def message(self) -> str:
        return 'Something went wrong.'

    def template(self) -> str:
        return 'error'

    def page_title(self) -> str:
        return 'Internal Server Error'
