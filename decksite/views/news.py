from typing import List

from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use
class News(View):
    def __init__(self, news: List[Container]) -> None:
        super().__init__()
        self.news = news

    def page_title(self):
        return 'News'
