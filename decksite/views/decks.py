from decksite.view import View


class Decks(View):
    def __init__(self, league_only: bool = False) -> None:
        super().__init__()
        self.show_seasons = True
        self.league_only = self.hide_top8 = self.show_omw = self.hide_source = league_only

    def page_title(self) -> str:
        deck_type = 'League ' if self.league_only else ''
        return f'{self.season_name()} {deck_type}Decks'
