from decksite.view import View

# pylint: disable=no-self-use
class TournamentLeaderboards(View):
    def __init__(self, series):
        self.series = series
        self.leaderboards = [s['entries'] for s in series] # These will be prepared in View.

    def subtitle(self):
        return 'Tournament Leaderboards'
