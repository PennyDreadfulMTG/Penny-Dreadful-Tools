from decksite.data import query
from decksite.deck_type import DeckType


def test_decks_where() -> None:
    args = {'deckType': DeckType.LEAGUE.value}
    assert "= 'League'" in query.decks_where(args, False, 1)
    assert "d.retired" in query.decks_where(args, False, 1)
    assert "d.retired" not in query.decks_where(args, True, 1)
    args = {'deckType': DeckType.TOURNAMENT.value}
    assert "= 'Gatherling'" in query.decks_where(args, False, 1)
    args = {'deckType': DeckType.ALL.value}
    assert "= 'League'" not in query.decks_where(args, False, 1)
    assert "= 'Gatherling'" not in query.decks_where(args, False, 1)

def test_card_search_where() -> None:
    tests = {
        'Tasigur, the Golden Fang': "name IN ('Tasigur, the Golden Fang')",
        # This test will not pass until we support `banned`.
        # 'banned:vintage cmc=6 c:g': "name IN ('Rebirth')",
        # The following tests might be flakey because database order matters
        'f:modern c:r "of the" moon': "name IN ('Call of the Full Moon', 'Magus of the Moon')",
        'f:modern c:r cmc=3 o:"nonbasic lands are mountains"': "name IN ('Blood Moon', 'Magus of the Moon')"
    }
    for q, expected in tests.items():
        assert expected == query.card_search_where(q)
