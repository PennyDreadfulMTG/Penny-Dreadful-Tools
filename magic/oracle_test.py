from magic import oracle

def test_legal():
    cards = oracle.load_cards(['Black Lotus', 'Armed // Dangerous', 'Séance'])
    assert not oracle.legal(cards)
    assert oracle.legal(cards, 'Vintage')
    cards = oracle.load_cards(['Plains', 'Island', 'Swamp', 'Mountain', 'Forest'])
    assert oracle.legal(cards)
    assert oracle.legal(cards, 'Modern')

def test_split_cards_query():
    cards = oracle.cards_from_query('Far/Away')
    assert len(cards) == 1
    assert cards[0].name == 'Far // Away'
