from typing import List

from decksite.data.person import Person
from decksite.view import View


# pylint: disable=no-self-use
class People(View):
    def __init__(self, people: List[Person]) -> None:
        super().__init__()
        self.people = people
        self.show_seasons = True

    def page_title(self):
        return 'People'
