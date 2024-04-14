import pytest

from decksite.data import query
from decksite.deck_type import DeckType
from shared.pd_exception import InvalidArgumentException


def test_decks_where() -> None:
    args = {'deckType': DeckType.LEAGUE.value}
    assert "= 'League'" in query.decks_where(args, False, 1)
    assert 'd.retired' in query.decks_where(args, False, 1)
    assert 'd.retired' not in query.decks_where(args, True, 1)
    args = {'deckType': DeckType.TOURNAMENT.value}
    assert "= 'Gatherling'" in query.decks_where(args, False, 1)
    args = {'deckType': DeckType.ALL.value}
    assert "= 'League'" not in query.decks_where(args, False, 1)
    assert "= 'Gatherling'" not in query.decks_where(args, False, 1)

def test_card_search_where() -> None:
    tests = {
        'Tasigur, the Golden Fang': ("name IN ('Tasigur, the Golden Fang')", ''),
        # This test will not pass until we support `banned`.
        # 'banned:vintage cmc=6 c:g': "name IN ('Rebirth')",
        # The following tests might be flakey because database order matters
        'f:modern c:r "of the" moon': ("name IN ('Call of the Full Moon', 'Magus of the Moon')", ''),
        'f:modern c:r cmc=3 o:"nonbasic lands are mountains"': ("name IN ('Blood Moon', 'Magus of the Moon')", ''),
        'c:bm': ('FALSE', "Using 'm' with other colors is not supported, use 'color>b' instead"),
    }
    for q, (expected, message) in tests.items():
        assert (expected, message) == query.card_search_where(q)


def test_limit() -> None:
    args = {'page': '1', 'pageSize': '150'}
    assert query.pagination(args) == (1, 150, 'LIMIT 150, 150')
    args = {}
    assert query.pagination(args) == (0, 20, 'LIMIT 0, 20')
    with pytest.raises(InvalidArgumentException):
        args = {'page': '1', 'pageSize': '20000'}
        query.pagination(args)
    with pytest.raises(InvalidArgumentException):
        args = {'page': 'nonsensical', 'pageSize': 'nonsensical'}
        query.pagination(args)
