from typing import List

from decksite.data import person as ps
from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use
class PersonAchievements(View):
    def __init__(self, person: ps.Person, achievements: List[Container]) -> None:
        super().__init__()
        self.person = person
        self.achievements = achievements
        self.show_seasons = True
        self.show_active_runs_text = False
        self.decks = []
        for a in achievements:
            if a.detail is not None:
                self.decks += a.detail.decks

    def page_title(self):
        return f'Achievement details: {self.person.name}'
