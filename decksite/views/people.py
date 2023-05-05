from decksite.view import View


class People(View):
    def __init__(self) -> None:
        super().__init__()
        self.show_seasons = True

    def page_title(self) -> str:
        return 'People'
