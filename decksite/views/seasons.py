from decksite.view import View


# pylint: disable=no-self-use
class Seasons(View):
    def __init__(self) -> None:
        super().__init__()
        self.seasons = self.all_seasons()
        self.seasons.pop() # Don't show "all time" on this page as it is not fully supported yet.

    def page_title(self) -> str:
        return 'Past Seasons'
