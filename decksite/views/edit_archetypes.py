from decksite.view import View

# pylint: disable=no-self-use
class EditArchetypes(View):
    def __init__(self, archetypes, decks):
        self.archetypes = archetypes
        self.decks = decks

    def subtitle(self):
        return 'Edit Archetypes'
