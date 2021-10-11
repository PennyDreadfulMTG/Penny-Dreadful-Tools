from typing import List

from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use
class Banners(View):
    def __init__(self, cards: List[Container]) -> None:
        super().__init__()
        self.banners = cards

    def page_title(self) -> str:
        return 'Banner Info'
