from typing import Sequence

from decksite.view import View
from magic.models import Deck
from shared import dtutil


# pylint: disable=no-self-use
class EditMatches(View):
    def __init__(self, competition_id: int, decks: Sequence[Deck]) -> None:
        super().__init__()
        self.competition_id = competition_id
        far_future = dtutil.parse('2100-01-01', '%Y-%m-%d', dtutil.UTC_TZ)
        self.decks = sorted(decks, key=lambda d: d.person + str((far_future - d.created_date).total_seconds()))

    def page_title(self) -> str:
        return 'Edit Matches'
