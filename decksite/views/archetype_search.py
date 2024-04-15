from decksite import prepare
from decksite.data import archetype
from decksite.data.archetype import Archetype
from decksite.view import View
from magic.models import Deck


class ArchetypeSearch(View):
    def __init__(self, archetypes: list[Archetype], search_results: list[Deck], q: str, notq: str) -> None:
        super().__init__()
        self.archetypes = archetypes
        self.archetypes_preordered = archetype.preorder(archetypes)

        self.has_search_results = len(search_results) > 0
        self.search_results = search_results
        for d in self.search_results:
            prepare.prepare_deck(d)
        self.query = q
        self.notquery = notq

    def page_title(self) -> str:
        return 'Edit Archetypes'
