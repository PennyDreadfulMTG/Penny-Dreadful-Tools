from decksite import league
from decksite.view import View

# pylint: disable=no-self-use
class SignUp(View):
    def __init__(self, form):
        self.form = form
        self.league = league.active_league()

    def subtitle(self):
        return '{league} Sign Up'.format(league=self.league['name'])
