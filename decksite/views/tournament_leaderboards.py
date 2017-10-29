from magic import tournaments

from decksite.view import View

# pylint: disable=no-self-use
class TournamentLeaderboards(View):
    def __init__(self):
        info = tournaments.next_tournament_info()
        self.next_tournament_name = info['next_tournament_name']
        self.next_tournament_time = info['next_tournament_time']

        self.tournaments = [
            {
                'name': 'Penny Dreadful Mondays',
            },
            {
                'name': 'Penny Dreadful Thursdays',
            },
            {
                'name': 'Penny Dreadful Sundays',
            }
        ]

    def subtitle(self):
        return 'Tournament Leaderboards'
