from collections.abc import Iterable

from decksite.data.person import Person
from decksite.view import View


class Ban(View):
    def __init__(self, banned_people: Iterable[Person], success: bool | None) -> None:
        super().__init__()
        self.person_filter = 'unbanned'
        self.banned_people = banned_people
        if success is not None:
            self.message = 'Operation ' + ('succeeded' if success else 'failed')

    def page_title(self) -> str:
        return 'Ban'
