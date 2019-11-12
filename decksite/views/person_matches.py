from typing import List

from decksite.data import person as ps
from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use
class PersonMatches(View):
    def __init__(self, person: ps.Person, matches: List[Container]) -> None:
        super().__init__()
        self.person = person
        self.matches = matches

    def page_title(self) -> str:
        return f'{self.person.name} Matches'
