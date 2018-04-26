from flask import url_for
from flask_babel import gettext

from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class Report(LeagueForm):
    def __init__(self, form, person_id=None) -> None:
        super().__init__(form)
        self.retire_url = url_for('retire')
        self.person_id = person_id
        self.logout_url = url_for('logout', target='report')

    def page_title(self):
        return '{league} Result Report'.format(league=self.league['name'])

    def TT_REPORT(self):
        return gettext('Report')

    def TT_YOUR_DECK(self):
        return gettext('Your Deck')
