from typing import List

from flask import url_for

from decksite.data import archetype as archs
from decksite.deck_type import DeckType
from decksite.view import View


# pylint: disable=no-self-use, too-many-instance-attributes
class Archetypes(View):
    def __init__(self, archetypes: List[archs.Archetype], tournament_only: bool = False) -> None:
        super().__init__()
        self.archetypes = archetypes
        self.decks = []
        self.show_seasons = True
        self.tournament_only = self.hide_source = self.hide_perfect_runs = tournament_only
        self.show_tournament_toggle = True
        self.toggle_results_url = url_for('.archetypes', deck_type=None if tournament_only else DeckType.TOURNAMENT.value)

    def page_title(self) -> str:
        return 'Archetypes'
