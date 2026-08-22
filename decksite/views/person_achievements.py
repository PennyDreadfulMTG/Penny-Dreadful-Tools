from decksite.data import person as ps
from decksite.view import View
from shared.container import Container


class PersonAchievements(View):
    def __init__(self, person: ps.Person, achievements: list[Container], season_active: list[int]) -> None:
        super().__init__()
        self.person = person
        self.is_person_page = True
        self.achievements = achievements
        self.show_seasons = True
        self.legal_seasons = list(season_active)
        if len([a for a in achievements if a.legend]) == 0:
            self.no_achievements = True

    def prepare_decks(self) -> None:
        super().prepare_decks()
        for achievement in self.achievements:
            if achievement.detail is not None:
                achievement.detail.hide_active_runs = self.hide_active_runs
                self.prepare_active_runs(achievement.detail)

    def page_title(self) -> str:
        return f'{self.person.name} Achievements'
