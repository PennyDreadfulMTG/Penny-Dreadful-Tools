from flask import url_for

from decksite.view import View
from magic import tournaments


class Tournaments(View):
    def __init__(self) -> None:
        super().__init__()
        self.setup_tournaments()
        self.setup_tournament_rounds()
        self.leaderboards_url = url_for('.tournament_leaderboards')
        self.bugs_url = url_for('bugs')
        self.prizes = tournaments.normal_prizes()
        self.kickoff_url = url_for('kickoff')
        self.pd500_url = url_for('pd500')

    def page_title(self) -> str:
        return 'Cardhoarder Tournaments'
