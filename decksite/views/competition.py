from decksite.view import View

# pylint: disable=no-self-use
class Competition(View):
    def __init__(self, competition):
        self.competition = competition
        self.decks = competition.decks
        self.hide_source = True

    def __getattr__(self, attr):
        return getattr(self.competition, attr)

    def subtitle(self):
        return self.competition.name
