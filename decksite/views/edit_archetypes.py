from decksite.data import deck
from decksite.view import View


# pylint: disable=no-self-use
class EditArchetypes(View):
    def __init__(self, archetypes, search_results) -> None:
        super().__init__()
        self.archetypes = archetypes
        self.roots = [a for a in self.archetypes if a.is_root]
        self.queue = deck.load_decks(where='NOT d.reviewed', order_by='updated_date DESC', limit='LIMIT 10')
        deck.load_similar_decks(self.queue)
        for d in self.queue:
            if len(d.similar_decks) > 0:
                d.suggestion = d.similar_decks[0]
                self.prepare_deck(d.suggestion)
        for d in self.queue:
            self.prepare_deck(d)
        self.has_search_results = len(search_results) > 0
        self.search_results = search_results
        for d in self.search_results:
            self.prepare_deck(d)

    def page_title(self):
        return 'Edit Archetypes'
