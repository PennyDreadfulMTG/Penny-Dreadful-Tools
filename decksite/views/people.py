from typing import Sequence

from decksite.data.person import Person
from decksite.view import View


# pylint: disable=no-self-use
class People(View):
    def __init__(self, people: Sequence[Person]) -> None:
        super().__init__()
        self.people = people
        self.show_seasons = True

    def page_title(self):
        return 'People'
