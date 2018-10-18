from typing import List

from flask import url_for

from decksite.data import archetype as archs
from decksite.view import View
from shared.pd_exception import DoesNotExistException


# pylint: disable=no-self-use, too-many-instance-attributes
class Archetype(View):
    def __init__(self,
                 archetype: archs.Archetype,
                 archetypes: List[archs.Archetype],
                 matchups,
                 season_id: int) -> None:
        super().__init__()
        if not archetype:
            raise DoesNotExistException('No archetype supplied to view.')
        self.archetype = next(a for a in archetypes if a.id == archetype.id) if archetypes else archetype
        self.archetype.decks = archetype.decks
        # Load the deck information from archetype into skinny archetype loaded by load_archetypes_deckless_for with tree information.
        self.archetypes = archetypes
        self.decks = self.archetype.decks
        self.roots = [a for a in self.archetypes if a.is_root]
        matchup_archetypes = archs.load_archetypes_deckless(season_id=season_id)
        matchups_by_id = {m.id: m for m in matchups}
        for m in matchup_archetypes:
            # Overwite totals with vs-archetype specific details. Wipe out if there are none.
            m.update(matchups_by_id.get(m.id, {'hide_archetype': True}))
        for m in matchup_archetypes:
            self.prepare_archetype(m, matchup_archetypes)
        # Storing this in matchups_container like this lets us include two different archetype trees on the same page without collision.
        self.matchups_container = [{
            'is_matchups': True,
            'roots': [m for m in matchup_archetypes if m.is_root],
        }]
        self.show_seasons = True
        self.show_archetype = any(d.archetype_id != self.archetype.id for d in self.decks)
        self.show_archetype_tree = len(self.archetypes) > 0

    def og_title(self):
        return self.archetype.name

    def og_url(self):
        return url_for('archetype', archetype_id=self.archetype.id, _external=True)

    def og_description(self):
        return 'Penny Dreadful {name} archetype'.format(name=self.archetype.name)

    def __getattr__(self, attr):
        return getattr(self.archetype, attr)

    def page_title(self):
        return self.archetype.name
