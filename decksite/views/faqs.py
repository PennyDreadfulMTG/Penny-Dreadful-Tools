from decksite.view import View


# pylint: disable=no-self-use
class Faqs(View):
    def __init__(self) -> None:
        super().__init__()
        self.hide_intro = True # It has the same content as this page so don't repeat.

    def page_title(self):
        return 'Frequently Asked Questions'
