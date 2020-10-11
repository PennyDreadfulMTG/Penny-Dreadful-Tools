from typing import Any, Dict, List

from decksite.view import View


# pylint: disable=no-self-use
class TournamentLeaderboards(View):
    def __init__(self, series: List[Dict[str, Any]]) -> None:
        super().__init__()
        self.series = series
        self.show_seasons = True

    def page_title(self) -> str:
        return 'Tournament Leaderboards'
