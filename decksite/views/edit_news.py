from typing import List

from decksite.view import View
from shared.container import Container


class EditNews(View):
    def __init__(self, news: List[Container]) -> None:
        super().__init__()
        self.news = news

    def page_title(self) -> str:
        return 'Edit News'
