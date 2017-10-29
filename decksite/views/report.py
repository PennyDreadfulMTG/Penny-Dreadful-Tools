from flask import url_for

from decksite.views import LeagueForm

# pylint: disable=no-self-use
class Report(LeagueForm):
    def __init__(self, form):
        super().__init__(form)
        self.retire_url = url_for('retire')

    def subtitle(self):
        return '{league} Result Report'.format(league=self.league['name'])
