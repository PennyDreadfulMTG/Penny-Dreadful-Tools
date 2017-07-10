from decksite.view import View

# pylint: disable=no-self-use
class Archetypes(View):
    def __init__(self, archetypes):
        self.archetypes = archetypes
        self.decks = []

    def subtitle(self):
        return 'Archetypes'
