from flask import url_for

from shared.container import Container

from decksite.view import View

# pylint: disable=no-self-use, too-many-instance-attributes
class Competition(View):
    def __init__(self, competition):
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
                    leaderboard[d.person_id] = Container({'person': d.person, 'url': url_for('person', person_id=d.person_id), 'points': 0})
                leaderboard[d.person_id]['points'] += points
            if len(leaderboard) > 0:
                self.has_leaderboard = True
                self.leaderboard = sorted(leaderboard.values(), key=lambda k: k['points'], reverse=True)
                pos = 1
                for p in self.leaderboard:
                    p.finish = pos
                    p.stage_reached = 1
                    p.position = chr(9311 + pos) # ①, ②, ③, …
                    pos += 1
                    if pos > 8:
                        break

    def __getattr__(self, attr):
        return getattr(self.competition, attr)

    def subtitle(self):
        return self.competition.name
