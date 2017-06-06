from flask import url_for

from decksite.view import View

# pylint: disable=no-self-use
class Competition(View):
    def __init__(self, competition):
        self.competition = competition
        self.decks = competition.decks
        self.hide_source = True
        if competition.type == 'League':
            leaderboard = {}
            for d in competition.decks:
                bonus = 0
                if d.wins == 5:
                    bonus = 1
                points = d.wins + bonus
                if d.person_id not in leaderboard:
                    leaderboard[d.person_id] = {'person': d.person, 'url': url_for('person', person_id=d.person_id), 'points': 0}
                leaderboard[d.person_id]['points'] += points
            if len(leaderboard) > 0:
                self.has_leaderboard = True
                self.leaderboard = sorted(leaderboard.values(), key=lambda k: k['points'], reverse=True)

    def __getattr__(self, attr):
        return getattr(self.competition, attr)

    def subtitle(self):
        return self.competition.name
