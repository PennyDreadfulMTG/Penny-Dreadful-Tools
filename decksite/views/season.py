from decksite.view import View
from magic import rotation


# pylint: disable=no-self-use
class Season(View):
    def __init__(self, season, league_only) -> None:
        super().__init__()
        self.season = season
        self.decks = season.decks
        self.league_only = self.show_omw = self.hide_source = league_only
        self.show_seasons = True

    def page_title(self):
        return rotation.season_name(self.season.number)

    def __getattr__(self, attr):
        return getattr(self.season, attr)
