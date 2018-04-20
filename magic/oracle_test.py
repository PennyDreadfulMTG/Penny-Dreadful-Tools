import pytest

from magic import oracle


def test_legality():
    card = oracle.load_card('Swamp')
    assert card is not None
    assert card.legalities['Standard'] == 'Legal'
    assert card.legalities['Modern'] == 'Legal'
    assert card.legalities['Legacy'] == 'Legal'
    assert card.legalities['Vintage'] == 'Legal'
    assert card.legalities['Penny Dreadful'] == 'Legal'
    card = oracle.load_card('Black Lotus')
    assert card is not None
    assert 'Standard' not in card.legalities.keys()
    assert 'Modern' not in card.legalities.keys()
    assert card.legalities['Legacy'] == 'Banned'
    assert card.legalities['Vintage'] == 'Restricted'
    assert 'Penny Dreadful' not in card.legalities.keys()

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

# Check that the list of legal cards is being fetched correctly.
@pytest.mark.functional
def test_legality_list() -> None:
    legal_cards = oracle.legal_cards()
    assert len(legal_cards) > 0
