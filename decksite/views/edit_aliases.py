from collections.abc import Sequence

from decksite.data.person import Person
from decksite.view import View
from shared.container import Container


class EditAliases(View):
    def __init__(self, aliases: list[Container], all_people: Sequence[Person]) -> None:
        super().__init__()
        people_by_id = {p.id: p for p in all_people}
        for entry in aliases:
            entry.mtgo_username = people_by_id[entry.person_id].mtgo_username
        self.people = all_people
        self.aliases = aliases

    def page_title(self) -> str:
        return 'Edit Aliases'
