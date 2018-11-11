from flask import url_for

from decksite.data.form import Form
from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class Retire(LeagueForm):
    def __init__(self, form: Form) -> None:
        super().__init__(form)
        self.logout_url = url_for('logout', target='retire')

    def page_title(self) -> str:
        return 'Retire'
