from typing import List

from decksite.data import deck
from shared.container import Container


class Person(Container):
    __decks = None
    @property
    def decks(self) -> List[deck.Deck]:
        if self.__decks is None:
            self.__decks = deck.load_decks(f'd.person_id = {self.id}', season_id=self.season_id)
        return self.__decks
