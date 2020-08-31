from typing import Any, Dict

from decksite.view import View
from magic import tournaments
from shared import dtutil


# pylint: disable=no-self-use
class PD500(View):
    def __init__(self, leaderboard: Dict[str, Any]) -> None:
        super().__init__()
        self.entries = leaderboard['entries']
        self.leaderboards = [self.entries] # This will be prepared in View.
        self.next_pd500_date = dtutil.display_date_with_date_and_year(tournaments.next_pd500_date())

    def page_title(self) -> str:
        return 'The Penny Dreadful 500'
