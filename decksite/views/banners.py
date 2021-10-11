from typing import Dict

from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use
class Banners(View):
    def __init__(self, cards: Dict[int, Container]) -> None:
        super().__init__()
        self.banners = cards

    def page_title(self) -> str:
        return 'Banner Info'
