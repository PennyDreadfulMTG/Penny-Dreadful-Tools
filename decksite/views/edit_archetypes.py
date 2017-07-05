from decksite.data import deck
from decksite.view import View

# pylint: disable=no-self-use
class EditArchetypes(View):
    def __init__(self, archetypes, decks):
        self.archetypes = archetypes
        self.decks = decks
        self.roots = [a for a in self.archetypes if a.is_root]
        self.queue = deck.load_decks(where='d.archetype_id = 9 OR d.archetype_id IS NULL', order_by='updated_date DESC', limit='LIMIT 10')
        for d in self.queue:
            similar_decks = deck.get_similar_decks(d)
            if len(similar_decks) > 0:
                d.suggestion = similar_decks[0]
                self.prepare_deck(d.suggestion)
        for d in self.queue:
            self.prepare_deck(d)

    def subtitle(self):
        return 'Edit Archetypes'
