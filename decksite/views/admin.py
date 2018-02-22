from decksite.view import View


# pylint: disable=no-self-use
class Admin(View):
    def __init__(self, urls):
        self.urls = urls


    def subtitle(self):
        return 'Admin Menu'
