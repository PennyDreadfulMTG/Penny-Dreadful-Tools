from flask import url_for

from decksite.form import Form
from decksite.views.league_form import LeagueForm
from shared.container import Container


class Retire(LeagueForm):
    def __init__(self, form: Form, matches: list[Container]) -> None:
        super().__init__(form)
        self.logout_url = url_for('logout', target='retire')
        self.matches = matches
        self.show_matches = len(matches) > 0
        self.report_url = url_for('report')

    def page_title(self) -> str:
        return 'Retire'
