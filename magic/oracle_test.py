from magic import oracle
from magic.database import db


def test_legality():
    cards = oracle.cards_from_query('Swamp')
    assert len(cards) == 1
    assert cards[0].legalities['Standard'] == 'Legal'
    assert cards[0].legalities['Modern'] == 'Legal'
    assert cards[0].legalities['Legacy'] == 'Legal'
    assert cards[0].legalities['Vintage'] == 'Legal'
    assert cards[0].legalities['Penny Dreadful'] == 'Legal'
    cards = oracle.cards_from_query('Black Lotus')
    assert len(cards) == 1
    assert 'Standard' not in cards[0].legalities.keys()
    assert 'Modern' not in cards[0].legalities.keys()
    assert cards[0].legalities['Legacy'] == 'Banned'
    assert cards[0].legalities['Vintage'] == 'Restricted'
    assert 'Penny Dreadful' not in cards[0].legalities.keys()

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
    cards = oracle.cards_from_query('Fire // Ice')
    assert len(cards) == 1
    assert cards[0].name == 'Fire // Ice'
    cards = oracle.cards_from_query('Upheaval')
    assert len(cards) == 1
    assert cards[0].name == 'Upheaval'
    if db().is_sqlite():
        cards = oracle.cards_from_query('Uphaeval')
        assert len(cards) == 1
        assert cards[0].name == 'Upheaval'

def test_valid_name():
    assert oracle.valid_name('Dark Ritual') == 'Dark Ritual'
    assert oracle.valid_name('Far/Away') == 'Far // Away'

def test_load_cards():
    cards = oracle.load_cards(['Think Twice', 'Swamp'])
    assert len(cards) == 2
    assert 'Think Twice' in [c.name for c in cards]
    assert 'Swamp' in [c.name for c in cards]

def test_deck_sort_x_last():
    cards = oracle.load_cards(['Ghitu Fire', 'Flash of Insight', 'Frantic Search'])
    assert len(cards) == 3
    cards = {c.name: c for c in cards}
    assert oracle.deck_sort(cards.get('Ghitu Fire')) < oracle.deck_sort(cards.get('Flash of Insight'))
    assert oracle.deck_sort(cards.get('Ghitu Fire')) > oracle.deck_sort(cards.get('Frantic Search'))
