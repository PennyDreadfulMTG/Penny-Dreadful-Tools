from flask import url_for

from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use, too-many-instance-attributes
class Competition(View):
    def __init__(self, competition):
        super().__init__()
        self.competition = competition
        self.competitions = [self.competition]
        self.decks = competition.decks
        self.hide_source = True
        if competition.type == 'League':
            self.show_omw = True
            self.hide_top8 = True
            self.league_info_url = url_for('league')
            leaderboard = {}
            for d in competition.decks:
                if d.banned:
                    continue
                bonus = 0
                if d.wins >= 5:
                    bonus = 1
                points = d.wins + bonus
                if d.person_id not in leaderboard:
                    leaderboard[d.person_id] = Container({'person': d.person, 'person_id': d.person_id, 'points': 0, 'played': 0, 'retirements': 0})
                leaderboard[d.person_id]['points'] += points
                leaderboard[d.person_id]['played'] += d.wins + d.draws + d.losses
                leaderboard[d.person_id]['retirements'] += 1 if d.retired else 0
            if len(leaderboard) > 0:
                self.has_leaderboard = True
                self.leaderboard = sorted(leaderboard.values(), key=lambda k: (k['points'], k['played'], -k['retirements']), reverse=True)
                self.leaderboards = [self.leaderboard] # Will be prepared in View.

    def __getattr__(self, attr):
        return getattr(self.competition, attr)

    def subtitle(self):
        return self.competition.name
