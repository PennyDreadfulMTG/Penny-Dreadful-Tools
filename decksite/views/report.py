from typing import Optional

from flask import url_for
from flask_babel import gettext

from decksite.data.form import Form
from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class Report(LeagueForm):
    def __init__(self, form: Form, person_id: Optional[int] = None) -> None:
        super().__init__(form)
        self.retire_url = url_for('retire')
        self.person_id = person_id
        self.logout_url = url_for('logout', target='report')

    def page_title(self) -> str:
        return '{league} Result Report'.format(league=self.league['name'])

    def TT_REPORT(self) -> str:
        return gettext('Report')

    def TT_YOUR_DECK(self) -> str:
        return gettext('Your Deck')
