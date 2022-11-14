from typing import Optional, Iterable, List

from decksite.data.person import Person
from decksite.view import View


# pylint: disable=no-self-use
class Unlink(View):
    def __init__(self, people: Iterable[Person], num_affected_people: Optional[int] = None, errors: Optional[List[str]] = None) -> None:
        super().__init__()
        self.people = people
        if num_affected_people is not None:
            self.message = f'{num_affected_people} were affected'
        self.errors = errors or []

    def page_title(self) -> str:
        return 'Unlink'
