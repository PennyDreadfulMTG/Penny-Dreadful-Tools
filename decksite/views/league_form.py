from decksite import league
from decksite.form import Form
from decksite.view import View


class LeagueForm(View):
    def __init__(self, form: Form) -> None:
        super().__init__()
        self.form = form
        self.league = league.active_league()
        self.competitions = [self.league]
