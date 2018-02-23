from decksite.view import View


# pylint: disable=no-self-use
class Admin(View):
    def __init__(self, menu):
        self.menu = menu

    def subtitle(self):
        return 'Admin Menu'
