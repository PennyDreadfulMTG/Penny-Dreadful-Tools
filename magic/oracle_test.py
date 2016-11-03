from magic import oracle, legality

def test_legal_deck():
    # Consider changing these to other cards.  We don't want our test cases rotating in without warning.
    cards = oracle.load_cards(['Black Lotus', 'Armed // Dangerous', 'Séance'])
    assert not legality.legal_deck(cards)
    cards = oracle.load_cards(['Plains', 'Island', 'Swamp', 'Mountain', 'Forest'])
    assert legality.legal_deck(cards)

def test_cards_from_query():
    cards = oracle.cards_from_query('Far/Away')
    assert len(cards) == 1
    assert cards[0].name == 'Far // Away'
    cards = oracle.cards_from_query('Jötun Grunt')
    assert len(cards) == 1
    assert cards[0].name == 'Jötun Grunt'
    cards = oracle.cards_from_query('Jotun Grunt')
    assert len(cards) == 1
    assert cards[0].name == 'Jötun Grunt'
    cards = oracle.cards_from_query('Ready / Willing')
    assert len(cards) == 1
    assert cards[0].name == 'Ready // Willing'

def test_valid_name():
    assert oracle.valid_name('Dark Ritual') == 'Dark Ritual'
    assert oracle.valid_name('Far/Away') == 'Far // Away'
