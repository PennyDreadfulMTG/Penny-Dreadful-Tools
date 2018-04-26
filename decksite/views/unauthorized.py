from decksite.view import View


# pylint: disable=no-self-use
class Unauthorized(View):
    def __init__(self, error: str) -> None:
        super().__init__()
        if error:
            self.error = error

    def page_title(self):
        return 'Unauthorized'
