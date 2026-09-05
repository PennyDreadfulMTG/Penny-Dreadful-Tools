import re
from collections.abc import Callable

import pytest

from decksite.data import clauses
from decksite.deck_type import DeckType
from shared.pd_exception import InvalidArgumentException


@pytest.mark.parametrize('sort_order', ['ASC', 'DESC'])
@pytest.mark.parametrize(
    'order_by',
    [
        clauses.archetype_order_by,
        clauses.cards_order_by,
        clauses.people_order_by,
        clauses.head_to_head_order_by,
    ],
)
def test_win_percent_ordering_puts_nulls_last(
    order_by: Callable[[str | None, str | None], str],
    sort_order: str,
) -> None:
    sql = order_by('winPercent', sort_order)
    expression, ordered = sql.split(' IS NULL ASC, ', 1)

    assert ordered.startswith(f'{expression} {sort_order}')


def test_archetype_win_percent_auto_order_remains_descending() -> None:
    sql = clauses.archetype_order_by('winPercent', 'AUTO')
    expression, ordered = sql.split(' IS NULL ASC, ', 1)

    assert ordered.startswith(f'{expression} DESC')


@pytest.mark.parametrize('sort_by', ['quality', 'qualityOptimistic', 'qualityStrict', 'potential'])
@pytest.mark.parametrize('sort_order', ['ASC', 'DESC'])
def test_archetype_quality_ordering_puts_nulls_last(sort_by: str, sort_order: str) -> None:
    sql = clauses.archetype_order_by(sort_by, sort_order)
    expression, ordered = sql.split(' IS NULL ASC, ', 1)

    assert ordered.startswith(f'{expression} {sort_order}')


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

def test_decks_where_ignores_empty_card_name() -> None:
    # The deck table always sends cardName= (empty) from data-card-name="", which must not filter out every deck.
    from werkzeug.datastructures import MultiDict
    assert 'FALSE' not in clauses.decks_where(MultiDict([('cardName', '')]), False, 1)
    assert 'FALSE' not in clauses.decks_where({'cardName': ''}, False, 1)

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

def test_order_by_auto() -> None:
    assert 'ASC' in clauses.cards_order_by('name', 'AUTO')
    assert 'DESC' in clauses.cards_order_by('numDecks', 'AUTO')
    assert 'ASC' in clauses.people_order_by('name', 'AUTO')
    assert 'DESC' in clauses.people_order_by('elo', 'AUTO')
    assert 'ASC' in clauses.head_to_head_order_by('name', 'AUTO')
    assert 'DESC' in clauses.head_to_head_order_by('numMatches', 'AUTO')
    assert 'ASC' in clauses.leaderboard_order_by('name', 'AUTO')
    assert 'DESC' in clauses.leaderboard_order_by('points', 'AUTO')
    assert 'ASC' in clauses.matches_order_by('person', 'AUTO')
    assert 'DESC' in clauses.matches_order_by('date', 'AUTO')
    assert 'ASC' in clauses.rotation_order_by('name', 'AUTO')
    assert 'DESC' in clauses.rotation_order_by('hits', 'AUTO')
    assert 'ASC' in clauses.decks_order_by('name', 'AUTO', None)
    assert 'DESC' in clauses.decks_order_by('date', 'AUTO', None)
    assert 'DESC' in clauses.archetype_order_by('quality', 'AUTO')
    assert 'ASC' in clauses.archetype_order_by('name', 'AUTO')

def test_top8_order_groups_tied_finishes_by_competition_for_application_tiebreaking() -> None:
    order_by = clauses.decks_order_by('top8', 'AUTO', None)

    assert order_by.index('d.finish ASC') < order_by.index('c.start_date) DESC')
    assert order_by.index('c.start_date) DESC') < order_by.index('d.competition_id ASC')
    assert order_by.index('d.competition_id ASC') < order_by.index('d.person_id ASC')
    assert 'deck_match' not in order_by

def test_only_top8_order_uses_swiss_tiebreakers() -> None:
    assert clauses.decks_order_uses_swiss_tiebreakers('top8', None)
    assert clauses.decks_order_uses_swiss_tiebreakers(None, '123')
    assert not clauses.decks_order_uses_swiss_tiebreakers('date', '123')
    assert not clauses.decks_order_uses_swiss_tiebreakers(None, None)

def test_cards_where_single(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clauses.oracle, 'valid_name', lambda name: name)
    result = clauses.cards_where(['Hive Mind'])
    assert "deck_card WHERE card = 'Hive Mind'" in result

def test_cards_where_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clauses.oracle, 'valid_name', lambda name: name)
    result = clauses.cards_where(['Hive Mind', 'Lake of the Dead'])
    assert 'HAVING COUNT(DISTINCT card) = 2' in result
    assert "'Hive Mind'" in result
    assert "'Lake of the Dead'" in result

def test_cards_where_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    def invalid_name(_name: str) -> str:
        raise clauses.InvalidDataException()

    monkeypatch.setattr(clauses.oracle, 'valid_name', invalid_name)
    assert clauses.cards_where(['Not a Card']) == 'FALSE'

def test_decks_where_min_win_rate() -> None:
    args: dict[str, str] = {'minWinRate': '50'}
    result = clauses.decks_where(args, True, None)
    assert 'cache.wins' in result
    assert '50.0' in result

def test_decks_where_min_win_rate_invalid() -> None:
    from shared.pd_exception import InvalidArgumentException
    args: dict[str, str] = {'minWinRate': 'abc'}
    with pytest.raises(InvalidArgumentException):
        clauses.decks_where(args, True, None)

def test_decks_where_min_win_rate_out_of_range() -> None:
    from shared.pd_exception import InvalidArgumentException
    args: dict[str, str] = {'minWinRate': '150'}
    with pytest.raises(InvalidArgumentException):
        clauses.decks_where(args, True, None)

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
