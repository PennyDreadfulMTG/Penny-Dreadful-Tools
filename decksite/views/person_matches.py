from decksite.data import person as ps
from decksite.view import View
from shared.container import Container


class PersonMatches(View):
    def __init__(self, person: ps.Person, matches: list[Container]) -> None:
        super().__init__()
        self.person = person
        self.matches = matches

    def page_title(self) -> str:
        return f'{self.person.name} Matches'
