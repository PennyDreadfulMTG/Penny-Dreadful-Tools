from decksite.view import View

# pylint: disable=no-self-use
class TournamentLeaderboards(View):
    def __init__(self):
        # get all the Gatherling series leaderboards out of db.
        # per-person, per-series, decks only in the dates of this season, point per win, point for showing up.
        # Use leaderboard code in views/competition, probably
        self.tournaments = [
            {
                'name': 'Penny Dreadful Saturdays',
            },
            {
                'name': 'Penny Dreadful Sundays',
            },
            {
                'name': 'Penny Dreadful Mondays',
            },
            {
                'name': 'Penny Dreadful Thursdays',
            },
        ]

    def subtitle(self):
        return 'Tournament Leaderboards'
