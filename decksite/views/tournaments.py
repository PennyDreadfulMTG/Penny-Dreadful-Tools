from flask import url_for

from decksite.view import View
from magic import tournaments


# pylint: disable=no-self-use
class Tournaments(View):
    def __init__(self) -> None:
        super().__init__()
        self.setup_tournaments()
        self.leaderboards_url = url_for('.tournament_leaderboards')
        self.bugs_url = url_for('bugs')
        self.prizes = tournaments.prizes_by_finish()

    def page_title(self) -> str:
        return 'Tournaments'
