from decksite.view import View
from decksite import league

# pylint: disable=no-self-use
class Competition(View):
    def __init__(self, competition):
        self.competition = competition
        self.decks = competition.decks
        self.hide_source = True

    def __getattr__(self, attr):
        return getattr(self.competition, attr)

    def subtitle(self):
        return self.competition.name

    def is_league(self):
        return self.competition.id == league.get_active_competition_id()
        # return self.competition.type == "League"
