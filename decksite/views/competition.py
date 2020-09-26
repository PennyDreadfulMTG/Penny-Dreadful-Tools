from typing import Any, Dict

from decksite.data.competition import Competition as Comp
from decksite.view import View
from shared import dtutil
from shared.container import Container


# pylint: disable=no-self-use, too-many-instance-attributes
class Competition(View):
    def __init__(self, competition: Comp) -> None:
        super().__init__()
        self.competition = competition
        self.competitions = [self.competition]
        self.decks = competition.decks
        self.hide_source = True
        if competition.type == 'League':
            self.show_omw = True
            self.hide_top8 = True
            leaderboard: Dict[int, Any] = {}
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

                for p in self.leaderboard:
                    p.score = (p.points, p.played, p.retirements)
                self.leaderboards = [self.leaderboard] # Will be prepared in View.
        else:
            self.has_external_source = True
        self.date = dtutil.display_date(competition.start_date)
        self.sponsor_name = competition.sponsor_name


    def __getattr__(self, attr: str) -> Any:
        return getattr(self.competition, attr)

    def page_title(self) -> str:
        return self.competition.name
