from decksite.view import View

# pylint: disable=no-self-use
class EditArchetypes(View):
    def __init__(self, archetypes, decks):
        self.archetypes = archetypes
        self.decks = decks
        self.roots = [a for a in self.archetypes if a.is_root]

    def subtitle(self):
        return 'Edit Archetypes'
