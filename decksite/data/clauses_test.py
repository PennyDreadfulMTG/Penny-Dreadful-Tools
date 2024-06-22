import re

import pytest

from decksite.data import clauses
from decksite.deck_type import DeckType
from shared.pd_exception import InvalidArgumentException


def test_decks_where() -> None:
    args = {'deckType': DeckType.LEAGUE.value}
    assert "= 'League'" in clauses.decks_where(args, False, 1)
    assert 'd.retired' in clauses.decks_where(args, False, 1)
    assert 'd.retired' not in clauses.decks_where(args, True, 1)
    args = {'deckType': DeckType.TOURNAMENT.value}
    assert "= 'Gatherling'" in clauses.decks_where(args, False, 1)
    args = {'deckType': DeckType.ALL.value}
    assert "= 'League'" not in clauses.decks_where(args, False, 1)
    assert "= 'Gatherling'" not in clauses.decks_where(args, False, 1)


def test_card_search_where() -> None:
    assert ("name IN ('Tasigur, the Golden Fang')", '') == clauses.card_search_where('Tasigur, the Golden Fang')
    assert ("cs.name IN ('Tasigur, the Golden Fang')", '') == clauses.card_search_where('Tasigur, the Golden Fang', column_name='cs.name')
    # This test will not pass until we support `banned`.
    # 'banned:vintage cmc=6 c:g': "name IN ('Rebirth')",
    where, message = clauses.card_search_where('f:modern c:r "of the" moon')
    assert message == ''
    found = re.search(r"name IN \('([^']+)', '([^']+)'\)", where)
    assert found
    assert {found.group(1), found.group(2)} == {'Call of the Full Moon', 'Magus of the Moon'}
    where, message = clauses.card_search_where('f:modern c:r cmc=3 o:"nonbasic lands are mountains"')
    assert message == ''
    found = re.search(r"name IN \('([^']+)', '([^']+)'\)", where)
    assert found
    assert {found.group(1), found.group(2)} == {'Blood Moon', 'Magus of the Moon'}
    assert ('FALSE', "Using 'm' with other colors is not supported, use 'color>b' instead") == clauses.card_search_where('c:bm')


def test_limit() -> None:
    args = {'page': '1', 'pageSize': '150'}
    assert clauses.pagination(args) == (1, 150, 'LIMIT 150, 150')
    args = {}
    assert clauses.pagination(args) == (0, 20, 'LIMIT 0, 20')
    with pytest.raises(InvalidArgumentException):
        args = {'page': '1', 'pageSize': '20000'}
        clauses.pagination(args)
    with pytest.raises(InvalidArgumentException):
        args = {'page': 'nonsensical', 'pageSize': 'nonsensical'}
        clauses.pagination(args)
