from decksite.view import View
from magic.models import Competition


class Competitions(View):
    def __init__(self, competitions: list[Competition]) -> None:
        super().__init__()
        self.competitions = competitions
        self.show_seasons = True

    def page_title(self) -> str:
        return 'Competitions'
