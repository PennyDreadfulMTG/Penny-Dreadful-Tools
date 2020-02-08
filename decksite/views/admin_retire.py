from flask import url_for

from decksite.data.form import Form
from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class AdminRetire(LeagueForm):
    def __init__(self, form: Form) -> None:
        super().__init__(form)
        self.logout_url = url_for('logout', target='admin_retire')

    def page_title(self) -> str:
        return 'Retire Deck'
