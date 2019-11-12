from typing import List

from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use
class Achievements(View):
    def __init__(self, achievements: List[Container]) -> None:
        super().__init__()
        self.achievements = achievements
        self.leaderboards: List[List[Container]] = []
        for a in self.achievements:
            if a.leaderboard:
                self.leaderboards.append(a.leaderboard)
                a.has_leaderboard = True
        self.show_seasons = True

    def page_title(self) -> str:
        return 'Achievements'
