from decksite.view import View


# pylint: disable=no-self-use
class Faqs(View):
    def __init__(self):
        self.hide_intro = True # It has the same content as this page so don't repeat.

    def subtitle(self):
        return 'Frequently Asked Questions'
