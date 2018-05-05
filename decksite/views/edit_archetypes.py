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
            self.find_and_prepare_suggestion(d)
        for d in self.queue:
            self.prepare_deck(d)
        self.has_search_results = len(search_results) > 0
        self.search_results = search_results
        for d in self.search_results:
            self.prepare_deck(d)

    def find_and_prepare_suggestion(self, d: deck.Deck) -> None:
        if len(d.similar_decks) == 0:
            return
        d.suggestion = d.similar_decks[0]
        # Because we load similar decks for the whole queue all at once guard against "double-preparing" a similar deck.
        if not d.suggestion.get('prepared'):
            self.prepare_deck(d.suggestion)
            d.suggestion.prepared = True

    def page_title(self):
        return 'Edit Archetypes'

