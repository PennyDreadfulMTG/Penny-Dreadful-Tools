from decksite.view import View

# pylint: disable=no-self-use
class Archetypes(View):
    def __init__(self, archetypes):
        self.archetypes = archetypes
        self.decks = []
        for a in self.archetypes:
            for d in a.decks:
                self.decks.append(d)

    def subtitle(self):
        return 'Archetypes'
