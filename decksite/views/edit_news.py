from decksite.view import View


# pylint: disable=no-self-use
class EditNews(View):
    def __init__(self, news):
        super().__init__()
        self.news = news

    def subtitle(self):
        return 'Edit News'
