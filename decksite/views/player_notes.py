from typing import Iterable

from decksite.data.person import Person
from decksite.view import View
from shared import dtutil
from shared.container import Container


# pylint: disable=no-self-use
class PlayerNotes(View):
    def __init__(self, notes: Iterable[Container], people: Iterable[Person]) -> None:
        super().__init__()
        for n in notes:
            n.display_date = dtutil.display_date(n.created_date)
        self.notes = notes
        self.people = people

    def page_title(self):
        return 'Player Notes'
