import random

from .error import ErrorView


class BadRequest(ErrorView):
    def __init__(self, exception: Exception) -> None:
        super().__init__()
        self.exception = str(exception)
        self.card = super().make_card(random.choice(['Mistakes Were Made', 'Rookie Mistake', 'Uchbenbak, the Great Mistake']))
        self.cards = [self.card]

    def message(self) -> str:
        return f"That doesn't look right.  {self.exception}"

    def template(self) -> str:
        return 'error'

    def page_title(self) -> str:
        return 'Bad Request'
