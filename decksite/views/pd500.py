from flask import url_for

from decksite.view import View
from magic import tournaments
from shared import dtutil


# pylint: disable=no-self-use
class PD500(View):
    def __init__(self) -> None:
        super().__init__()
        self.leaderboards_url = url_for('seasons.tournament_leaderboards')
        self.next_pd500_date = dtutil.display_date(tournaments.next_pd500_date(), 2)

    def page_title(self) -> str:
        return 'The Penny Dreadful 500'
