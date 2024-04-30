from decksite.view import View
from shared.container import Container


class Banners(View):
    def __init__(self, cards: list[Container]) -> None:
        super().__init__()
        self.banners = cards

    def page_title(self) -> str:
        return 'Banner Info'
