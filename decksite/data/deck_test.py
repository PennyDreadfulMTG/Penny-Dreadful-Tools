from typing import List

from decksite.data import deck


def test_load_similar_decks() -> None:
    ds: List[deck.Deck] = []
    deck.load_similar_decks(ds)
    assert ds == []
    d = deck.Deck({'id': 0})
    d.maindeck = [{'n': 60, 'name': 'Ancestral Recall'}]
    d.sideboard = []
    deck.load_similar_decks([d])
    assert d.similar_decks == []
