from decksite.view import View


# pylint: disable=no-self-use
class Season(View):
    def __init__(self, season, league_only):
        self.season = season
        self.decks = season.decks
        self.league_only = self.show_omw = self.hide_source = league_only

    def subtitle(self):
        return 'Season {n}'.format(n=self.season.number)

    def __getattr__(self, attr):
        return getattr(self.season, attr)
