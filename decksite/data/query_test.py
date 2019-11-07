from decksite.data import query

def test_decks_where_deck_type() -> None:
    args = {'deckType': 'league'}
    assert "= 'League'" in query.decks_where(args)
    args = {'deckType': 'tournament'}
    assert "= 'Gatherling'" in query.decks_where(args)
    args = {'deckType': 'all'}
    assert "= 'League'" not in query.decks_where(args)
    assert "= 'Gatherling'" not in query.decks_where(args)

def test_decks_where_archetype_id() -> None:
    pass
