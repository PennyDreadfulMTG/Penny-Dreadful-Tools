from typing import Any

from magic import oracle
from shared.container import Container

from .card import Card


class CardRef(Container):
    __card = None

    def __init__(self, name: str, count: int) -> None:
        super().__init__()
        self['n'] = count
        self.name = name

    def __contains__(self, key: str) -> bool:
        if key == 'card':
            return True
        return super().__contains__(key)

    def __getitem__(self, key: str) -> Any:
        if key == 'card':
            return self.card
        return super().__getitem__(key)

    @property
    def card(self) -> Card:
        if self.__card is None:
            self.__card = oracle.cards_by_name()[self.name]
        return self.__card
