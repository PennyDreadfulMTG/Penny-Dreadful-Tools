from decksite.view import View


# pylint: disable=no-self-use
class News(View):
    def __init__(self, news) -> None:
        super().__init__()
        self.news = news

    def page_title(self):
        return 'News'
