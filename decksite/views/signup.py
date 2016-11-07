from decksite.views import LeagueForm

# pylint: disable=no-self-use
class SignUp(LeagueForm):
    def subtitle(self):
        return '{league} Sign Up'.format(league=self.league['name'])
