from decksite.data import person as ps
from decksite.view import View
from shared.container import Container


class PersonAchievements(View):
    def __init__(self, person: ps.Person, achievements: list[Container]) -> None:
        super().__init__()
        self.person = person
        self.is_person_page = True
        self.achievements = achievements
        self.show_seasons = True
        if len([a for a in achievements if a.legend]) == 0:
            self.no_achievements = True

    def page_title(self) -> str:
        return f'{self.person.name} Achievements'
