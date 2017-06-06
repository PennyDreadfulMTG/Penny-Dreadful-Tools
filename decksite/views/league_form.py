from decksite import league
from decksite.view import View

# pylint: disable=no-self-use
class LeagueForm(View):
    def __init__(self, form):
        self.form = form
        self.league = league.active_league()
        self.competitions = [self.league]
