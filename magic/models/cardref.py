from shared.container import Container
from magic import oracle
from .card import Card
class CardRef(Container):
    __card = None

    def __init__(self, name: str, count: int) -> None:
        super().__init__()
        self['n'] = count
        self.name = name

    @property
    def card(self) -> Card:
        if self.__card is None:
            self.__card = oracle.cards_by_name()[self.name]
        return self.__card
