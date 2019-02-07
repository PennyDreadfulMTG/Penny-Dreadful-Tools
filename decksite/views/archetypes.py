from typing import List

from flask import url_for

from decksite.data import archetype as archs
from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use, too-many-instance-attributes
class Archetypes(View):
    def __init__(self, archetypes: List[archs.Archetype],
                 all_matchups: List[Container],
                 tournament_only: bool = False
                ) -> None:
        min_matches_for_matchups_grid = 50 if not tournament_only else 20
        super().__init__()
        self.archetypes = archetypes
        self.decks = []
        self.roots = [a for a in self.archetypes if a.is_root]
        self.show_seasons = True
        self.tournament_only = tournament_only

        self.show_tournament_toggle = True

        if tournament_only:
            self.toggle_results_url = url_for('.archetypes')
        else:
            self.toggle_results_url = url_for('.archetypes_tournament')

        # We need to prepare the roots so we have the archetype tree available for traversal.
        # This is possibly a sign that something is in the wrong place.
        for r in self.roots:
            self.prepare_archetype(r, self.archetypes)

        for a in self.archetypes:
            a.matchups = []

            # if tournament_only, move the tournament data into the appropriate slots for the view
            def convert(m: Container) -> Container:
                if tournament_only:
                    m.win_percent = m.win_percent_tournament
                    m.wins = m.wins_tournament
                    m.losses = m.losses_tournament
                    m.draws = m.draws_tournament
                return m

            # in one pass, filter out matchups with no data so we can determine which
            #   archetypes to include on the table, and convert matchups appropriately
            if not tournament_only:
                matchups = [convert(m) for m in all_matchups if m.archetype_id == a.id]
            else:
                matchups = [convert(m) for m in all_matchups if (m.archetype_id == a.id and
                                                                 m.wins_tournament + m.losses_tournament + m.draws_tournament > 0)]

            if len(matchups) < min_matches_for_matchups_grid:
                a.show_in_matchups_grid = False
                continue
            a.show_in_matchups_grid = True
            matchups_by_id = {b.id: b for b in matchups}
            for root in self.roots:
                for b in root.archetype_tree:
                    mu = matchups_by_id.get(b.id)
                    if mu and mu.wins + mu.losses > 0:
                        mu.has_data = True
                        mu.win_percent = float(mu.win_percent)
                        mu.color_cell = True
                        mu.hue = 120 if mu.win_percent >= 50 else 0
                        mu.saturation = abs(mu.win_percent - 50) + 50
                        mu.lightness = 80
                        mu.opponent_archetype = b
                    else:
                        mu = Container()
                        mu.has_data = False
                        mu.win_percent = None
                        mu.color_cell = False
                        mu.opponent_archetype = b
                    a.matchups.append(mu)

        self.show_matchup_grid = False
        for a in self.archetypes:
            if a.show_in_matchups_grid:
                self.show_matchup_grid = True
                break

        # Now we have traversed the tree and worked out which archetypes we are going to show, annotate matchups with that information.
        for a in self.archetypes:
            for mu in a.matchups:
                if mu:
                    mu.show_in_matchups_grid = mu.opponent_archetype.show_in_matchups_grid

        self.num_archetypes = len([mu for mu in self.archetypes[0].matchups if mu.show_in_matchups_grid]) if self.archetypes else 0

    def page_title(self):
        return 'Archetypes'
