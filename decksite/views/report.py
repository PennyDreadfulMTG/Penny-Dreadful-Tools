from flask import url_for
from flask_babel import gettext

from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class Report(LeagueForm):
    def __init__(self, form, logged_person=None):
        super().__init__(form)
        self.retire_url = url_for('retire')
        self.logged_person = logged_person
        self.logout_url = url_for('logout', target='report')

    def subtitle(self):
        return '{league} Result Report'.format(league=self.league['name'])

    def TT_REPORT(self):
        return gettext('Report')

    def TT_YOUR_DECK(self):
        return gettext('Your Deck')
