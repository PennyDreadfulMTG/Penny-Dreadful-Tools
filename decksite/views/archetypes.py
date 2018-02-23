from decksite.view import View


# pylint: disable=no-self-use
class Archetypes(View):
    def __init__(self, archetypes):
        self.archetypes = archetypes
        self.decks = []
        self.roots = [a for a in self.archetypes if a.is_root]

    def subtitle(self):
        return 'Archetypes'
