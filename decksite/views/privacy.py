from decksite.view import View


class Privacy(View):
    def __init__(self) -> None:
        super().__init__()
        self.hide_intro = True

    def page_title(self) -> str:
        return 'Privacy Policy'
