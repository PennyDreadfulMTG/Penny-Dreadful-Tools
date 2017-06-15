from decksite.view import View

# pylint: disable=no-self-use
class Archetype(View):
    def __init__(self, archetype):
        self.archetype = archetype
        self.archetypes = [archetype]
        self.decks = archetype.decks

    def __getattr__(self, attr):
        return getattr(self.archetype, attr)

    def subtitle(self):
        return self.archetype.name
