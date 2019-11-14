from typing import List

from flask import url_for

from decksite.data import archetype as archs
from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use, too-many-instance-attributes
class Archetypes(View):
    def __init__(self, archetypes: List[archs.Archetype], all_matchups: List[Container], tournament_only: bool = False) -> None:
        min_matches_for_matchups_grid = 50 if not tournament_only else 20
        super().__init__()
        self.archetypes = archetypes
        self.decks = []
        self.show_seasons = True
        self.tournament_only = self.hide_source = tournament_only
        self.show_tournament_toggle = True
        if tournament_only:
            self.toggle_results_url = url_for('.archetypes')
            self.archetypes = [a for a in self.archetypes if a.num_decks_tournament > 0]
        else:
            self.toggle_results_url = url_for('.archetypes_tournament')
        self.setup_matchups(archetypes, all_matchups, min_matches_for_matchups_grid)

    def page_title(self) -> str:
        return 'Archetypes'
