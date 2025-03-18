from typing import Any

from decksite.data.archetype import Archetype
from decksite.view import View
from magic import tournaments
from magic.models import Competition as Comp
from shared import dtutil


class Competition(View):
    def __init__(self, competition: Comp, archetypes: list[Archetype]) -> None:
        super().__init__()
        self.competition = competition
        self.competitions = [self.competition]
        self.competition_id = self.competition.id
        self.hide_source = True
        self.has_external_source = competition.type != 'League'
        if competition.type == 'League':
            self.skinny_leaderboard = True  # Try and bunch it up on the right of decks table if at all possible.
            self.show_omw = True
            self.hide_top8 = True
            self.has_leaderboard = True
        self.date = dtutil.display_date(competition.start_date)
        self.archetypes = archetypes
        self.show_archetype_tree = len(self.archetypes) > 0
        self.hide_perfect_runs = self.tournament_only = competition.type != 'League'
        self.league_only = self.hide_tournament_results = competition.type == 'League'
        self.hide_cardhoarder = tournaments.is_super_saturday(self.competition)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.competition, attr)

    def page_title(self) -> str:
        return self.competition.name
