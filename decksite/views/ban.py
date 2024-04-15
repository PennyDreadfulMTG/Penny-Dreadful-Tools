from collections.abc import Iterable

from decksite.data.person import Person
from decksite.view import View


class Ban(View):
    def __init__(self, people: Iterable[Person], success: bool | None) -> None:
        super().__init__()
        self.people = [p for p in people if not p.banned]
        self.banned_people = [p for p in people if p.banned]
        if success is not None:
            self.message = 'Operation ' + ('succeeded' if success else 'failed')

    def page_title(self) -> str:
        return 'Ban'
