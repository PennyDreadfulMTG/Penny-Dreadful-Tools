from decksite.data import query
from decksite.deck_type import DeckType


def test_decks_where_deck_type() -> None:
    args = {'deckType': DeckType.LEAGUE.value}
    assert "= 'League'" in query.decks_where(args, 1)
    args = {'deckType': DeckType.TOURNAMENT.value}
    assert "= 'Gatherling'" in query.decks_where(args, 1)
    args = {'deckType': DeckType.ALL.value}
    assert "= 'League'" not in query.decks_where(args, 1)
    assert "= 'Gatherling'" not in query.decks_where(args, 1)

def test_decks_where_archetype_id() -> None:
    pass
