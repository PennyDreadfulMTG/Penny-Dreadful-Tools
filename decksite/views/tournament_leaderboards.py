from decksite.view import View


# pylint: disable=no-self-use
class TournamentLeaderboards(View):
    def __init__(self, series) -> None:
        super().__init__()
        self.series = series
        self.leaderboards = [s['entries'] for s in series] # These will be prepared in View.
        self.show_seasons = True

    def page_title(self):
        return 'Tournament Leaderboards'
