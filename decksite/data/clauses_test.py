import re

import pytest

from decksite.data import achievements, clauses
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

def test_card_where_resolves_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clauses.oracle, 'valid_name', lambda _name: 'Spider-Man Noir')
    assert clauses.card_where('Kroble, Envoy of the Bog') == "d.id IN (SELECT deck_id FROM deck_card WHERE card = 'Spider-Man Noir')"

def test_card_where_rejects_unknown_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def invalid_name(_name: str) -> str:
        raise clauses.InvalidDataException()

    monkeypatch.setattr(clauses.oracle, 'valid_name', invalid_name)
    assert clauses.card_where('Definitely Not a Card') == 'FALSE'

def test_decks_where_achievement_without_person_or_season(monkeypatch: pytest.MonkeyPatch) -> None:
    # Before fix: int(args.get('personId', '')) raised ValueError when personId was absent.
    monkeypatch.setattr(achievements, 'load_deck_ids', lambda key, person_id, season_id: set())
    args = {'achievementKey': 'some_key'}
    # Must not raise ValueError
    result = clauses.decks_where(args, True, None)
    assert 'd.person_id' not in result

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
