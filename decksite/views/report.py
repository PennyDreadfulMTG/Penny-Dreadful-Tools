from decksite.views import LeagueForm

# pylint: disable=no-self-use
class Report(LeagueForm):
    def subtitle(self):
        return '{league} Result Report'.format(league=self.league['name'])
