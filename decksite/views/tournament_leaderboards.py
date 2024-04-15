from typing import Any

from decksite.view import View


class TournamentLeaderboards(View):
    def __init__(self, series: list[dict[str, Any]]) -> None:
        super().__init__()
        self.series = series
        self.show_seasons = True

    def page_title(self) -> str:
        return 'Tournament Leaderboards'
