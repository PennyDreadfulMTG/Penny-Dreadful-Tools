from decksite.view import View
from shared.container import Container


class Achievements(View):
    def __init__(self, achievements: list[Container]) -> None:
        super().__init__()
        self.achievements = achievements
        self.leaderboards: list[list[Container]] = []
        for a in self.achievements:
            if a.leaderboard:
                self.leaderboards.append(a.leaderboard)
                a.has_leaderboard = True
        self.show_seasons = True

    def page_title(self) -> str:
        return 'Achievements'
