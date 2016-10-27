from magic import oracle

def test_legal():
    cards = oracle.load_cards(['Black Lotus', 'Armed // Dangerous', 'Séance'])
    assert not oracle.legal(cards)
    assert oracle.legal(cards, 'Vintage')
    cards = oracle.load_cards(['Plains', 'Island', 'Swamp', 'Mountain', 'Forest'])
    assert oracle.legal(cards)
    assert oracle.legal(cards, 'Modern')
