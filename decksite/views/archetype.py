from typing import Any, List

from flask import url_for

from decksite.data import archetype as archs
from decksite.deck_type import DeckType
from decksite.view import View
from shared.container import Container
from shared.pd_exception import DoesNotExistException


# pylint: disable=no-self-use, too-many-instance-attributes
class Archetype(View):
    # pylint: disable=too-many-arguments
    def __init__(self,
                 archetype: archs.Archetype,
                 archetypes: List[archs.Archetype],
                 matchups: List[Container],
                 season_id: int,
                 tournament_only: bool = False
                ) -> None:
        super().__init__()
        if not archetype:
            raise DoesNotExistException('No archetype supplied to view.')
        self.archetype = next(a for a in archetypes if a.id == archetype.id) if archetypes else archetype
        self.archetype.decks = archetype.decks
        # Load the deck information from archetype into skinny archetype loaded by load_archetypes_deckless_for with tree information.
        self.archetypes = archetypes
        self.tournament_only = self.hide_source = tournament_only
        matchup_archetypes = archs.load_archetypes_deckless(season_id=season_id)
        matchups_by_id = {m.id: m for m in matchups}
        for m in matchup_archetypes:
            # Overwite totals with vs-archetype specific details. Wipe out if there are none.
            m.update(matchups_by_id.get(m.id, {'hide_archetype': True}))
        # Prepare the second archetype tree manually becuase its archetypes don't have the standard name.
        for m in matchup_archetypes:
            self.prepare_archetype(m, matchup_archetypes)
        # Storing this in matchups_container like this lets us include two different archetype trees on the same page without collision.
        self.matchups_container = [{
            'is_matchups': True,
            'archetypes': matchup_archetypes,
        }]
        self.show_seasons = True
        self.show_tournament_toggle = True
        self.toggle_results_url = url_for('.archetype', archetype_id=self.archetype.id, deck_type=None if tournament_only else DeckType.TOURNAMENT.value)
        self.show_archetype = any(d.archetype_id != self.archetype.id for d in self.decks)
        self.show_archetype_tree = len(self.archetypes) > 0

    def og_title(self) -> str:
        return self.archetype.name

    def og_url(self) -> str:
        return url_for('.archetype', archetype_id=self.archetype.id, _external=True)

    def og_description(self) -> str:
        return 'Penny Dreadful {name} archetype'.format(name=self.archetype.name)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.archetype, attr)

    def page_title(self) -> str:
        return self.archetype.name
