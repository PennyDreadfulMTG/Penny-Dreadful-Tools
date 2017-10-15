from decksite.views import LeagueForm

# pylint: disable=no-self-use
class Retire(LeagueForm):
    def subtitle(self):
        return 'Retire'
