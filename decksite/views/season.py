from decksite.view import View

# pylint: disable=no-self-use
class Season(View):
    def __init__(self, season):
        self.season = season
        self.decks = season.decks

    def subtitle(self):
        return 'Season {n}'.format(n=self.season.number)

    def __getattr__(self, attr):
        return getattr(self.season, attr)
