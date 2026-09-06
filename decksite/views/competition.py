import datetime
from typing import Any

from flask import url_for

from decksite.data.archetype import Archetype
from decksite.view import View
from magic import seasons, tournaments
from magic.models import Competition as Comp
from shared import dtutil


def _exact_date(date: datetime.datetime) -> str:
    display = f'{date.astimezone(dtutil.WOTC_TZ):%b _%d_, %Y}'
    return dtutil.replace_day_with_ordinal(display)


class Competition(View):
    def __init__(self, competition: Comp, archetypes: list[Archetype]) -> None:
        super().__init__()
        self.competition = competition
        self.competitions = [self.competition]
        self.competition_id = self.competition.id
        self.hide_source = True
        self.has_external_source = competition.type != 'League'
        self.competition_dates = _exact_date(competition.start_date)
        if competition.type == 'League':
            self.skinny_leaderboard = True  # Try and bunch it up on the right of decks table if at all possible.
            self.show_omw = True
            self.hide_top8 = True
            self.has_leaderboard = True
            self.competition_dates = f'{self.competition_dates} – {_exact_date(competition.end_date)}'
        self.date = dtutil.display_date(competition.start_date)
        if competition.season_id:
            self.competition_season_name = seasons.season_name(competition.season_id)
            self.competition_season_url = url_for('seasons.competitions', season_id=competition.season_id)
        self.archetypes = archetypes
        self.show_archetype_tree = len(self.archetypes) > 0
        self.hide_perfect_runs = self.tournament_only = competition.type != 'League'
        self.league_only = self.hide_tournament_results = competition.type == 'League'
        self.hide_cardhoarder = tournaments.is_super_saturday(self.competition)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.competition, attr)

    def season_id(self) -> int:
        return self.competition.season_id or super().season_id()

    def page_title(self) -> str:
        return self.competition.name
