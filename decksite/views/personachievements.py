from typing import List

from decksite.view import View
from shared.container import Container

from decksite.data import person as ps


# pylint: disable=no-self-use
class PersonAchievements(View):
    def __init__(self, person: ps.Person, achievements: List[Container]) -> None:
        super().__init__()
        self.person = person
        self.achievements = achievements
        self.show_seasons = True

    def page_title(self):
        return f'Achievement details: {self.person.name}'
