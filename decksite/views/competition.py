from typing import Any

from decksite.data.competition import Competition as Comp
from decksite.view import View
from shared import dtutil


# pylint: disable=no-self-use, too-many-instance-attributes
class Competition(View):
    def __init__(self, competition: Comp) -> None:
        super().__init__()
        self.competition = competition
        self.competitions = [self.competition]
        self.decks = competition.decks
        self.hide_source = True
        self.has_external_source = competition.type != 'League'
        if competition.type == 'League':
            self.skinny_leaderboard = True # Try and bunch it up on the right of decks table if at all possible.
            self.show_omw = True
            self.hide_top8 = True
            self.has_leaderboard = True
        self.date = dtutil.display_date(competition.start_date)
        self.sponsor_name = competition.sponsor_name


    def __getattr__(self, attr: str) -> Any:
        return getattr(self.competition, attr)

    def page_title(self) -> str:
        return self.competition.name
