from decksite.view import View

# pylint: disable=no-self-use
class Archetype(View):
    def __init__(self, archetype, archetypes):
        self.archetype = archetype
        self.archetypes = archetypes
        self.decks = archetype.decks
        self.roots = [a for a in self.archetypes if a.is_root]

    def __getattr__(self, attr):
        return getattr(self.archetype, attr)

    def subtitle(self):
        return self.archetype.name
