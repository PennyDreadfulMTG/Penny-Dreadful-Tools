import inflect
from flask import url_for

from magic import tournaments

from decksite.view import View

# pylint: disable=no-self-use
class Tournaments(View):
    def __init__(self):

        info = tournaments.next_tournament_info()
        self.next_tournament_name = info['next_tournament_name']
        self.next_tournament_time = info['next_tournament_time']
        self.leaderboards_url = url_for('tournament_leaderboards')

        self.tournaments = [
            {
                'name': 'Penny Dreadful Saturdays',
                'hosts': ['Back_Alley_G', 'BigM'],
                'display_time': '1:30pm Eastern',
                'time': info['pdsat_time'],
                'chat_room': '#PDS'
            },
            {
                'name': 'Penny Dreadful Sundays',
                'hosts': ['bakert99', 'littlefield'],
                'display_time': '1:30pm Eastern',
                'time': info['pds_time'],
                'chat_room': '#PDS'
            },
            {
                'name': 'Penny Dreadful Mondays',
                'hosts': ['stash86', 'silasary'],
                'display_time': '7pm Eastern',
                'time': info['pdm_time'],
                'chat_room': '#PDM'
            },
            {
                'name': 'Penny Dreadful Thursdays',
                'hosts': ['silasary', 'stash86'],
                'display_time': '7pm Eastern',
                'time': info['pdt_time'],
                'chat_room': '#PDT'
            }
        ]
        p = inflect.engine()
        self.num_tournaments = p.number_to_words(len(self.tournaments))

    def subtitle(self):
        return 'Tournaments'
