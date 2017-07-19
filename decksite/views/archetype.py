from decksite.view import View

# pylint: disable=no-self-use
class Archetype(View):
    def __init__(self, archetype, archetypes):
        self.archetype = archetype
        archetype_with_record = next(a for a in archetypes if a.id == archetype.id)
        # Load the deck information from archetype into skinny archetype loaded by load_archetypes_deckless_for with tree information.
        self.archetype.update(archetype_with_record)
        self.archetypes = archetypes
        self.decks = self.archetype.decks
        self.roots = [a for a in self.archetypes if a.is_root]

    def __getattr__(self, attr):
        return getattr(self.archetype, attr)

    def subtitle(self):
        return self.archetype.name
