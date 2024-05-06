from decksite.data import deck
from shared.container import Container


class Person(Container):
    __decks = None

    @property
    def decks(self) -> list[deck.Deck]:
        if self.__decks is None:
            ds, _ = deck.load_decks(f'd.person_id = {self.id}', season_id=self.season_id)
            self.__decks = ds
        return self.__decks
