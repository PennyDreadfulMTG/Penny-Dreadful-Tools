from decksite.data import query

def test_decks_where_deck_type() -> None:
    args = {'deckType': 'league'}
    assert "= 'League'" in query.decks_where(args, 1)
    args = {'deckType': 'tournament'}
    assert "= 'Gatherling'" in query.decks_where(args, 1)
    args = {'deckType': 'all'}
    assert "= 'League'" not in query.decks_where(args, 1)
    assert "= 'Gatherling'" not in query.decks_where(args, 1)

def test_decks_where_archetype_id() -> None:
    pass
