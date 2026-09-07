from decksite import prepare
from decksite.view import View
from magic.models import Deck


class ArchetypeSearch(View):
    def __init__(self, search_results: list[Deck], q: str, notq: str) -> None:
        super().__init__()
        self.has_search_results = len(search_results) > 0
        self.search_results = search_results
        for d in self.search_results:
            prepare.prepare_deck(d)
        self.query = q
        self.notquery = notq

    def page_title(self) -> str:
        return 'Edit Archetypes'
