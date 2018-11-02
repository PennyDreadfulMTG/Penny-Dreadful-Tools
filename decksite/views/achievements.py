from flask import url_for

from decksite.view import View


# pylint: disable=no-self-use
class Achievements(View):
    def __init__(self, achievements):
        super().__init__()
        self.achievements = achievements
        self.leaderboards = []
        for a in self.achievements:
            if a.leaderboard:
                self.leaderboards.append(a.leaderboard)
                a.has_leaderboard = True
                a.leaderboard_heading = a.leaderboard_heading()
        self.show_seasons = True

    def page_title(self):
        return 'Achievements'
