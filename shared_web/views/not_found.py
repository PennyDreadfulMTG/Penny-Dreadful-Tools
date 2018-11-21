import random

from .error import ErrorView


# pylint: disable=no-self-use
class NotFound(ErrorView):
    def __init__(self, exception: Exception) -> None:
        super().__init__()
        self.exception = str(exception)
        self.card = super().make_card(random.choice(['Lost Order of Jarkeld', 'Totally Lost', 'Azusa, Lost but Seeking', 'Well of Lost Dreams', 'Shepherd of the Lost', 'Sphinx of Lost Truths', 'Lost in a Labyrinth', 'Vigil for the Lost', 'Lost Soul', 'Lost Leonin', 'Redeem the Lost', 'Lost Legacy', 'Lost in Thought', 'Lost in the Mist', 'Lost Auramancers', 'Lost Hours', 'Lost in the Woods', 'Altar of the Lost', 'Sovereigns of Lost Alara']))
        self.cards = [self.card]

    def message(self) -> str:
        return "We couldn't find that."

    def template(self) -> str:
        return 'error'

    def page_title(self) -> str:
        return 'Not Found'
