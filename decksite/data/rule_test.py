from unittest import mock

import pytest

from decksite.data import rule
from magic.models import Deck


def test_mistagged_decks_loads_decks_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = Deck({'id': 17})
    load_decks_by_id = mock.Mock(return_value=[expected])
    monkeypatch.setattr(rule, 'db', lambda: StubDatabase([{
        'deck_id': 17,
        'rule_id': 23,
        'rule_archetype_id': 42,
        'rule_archetype_name': 'Burn',
    }]))
    monkeypatch.setattr(rule.deck, 'load_decks_by_id', load_decks_by_id)

    result = rule.mistagged_decks()

    assert result == [expected]
    assert list(load_decks_by_id.call_args.args[0]) == [17]
    assert (expected.rule_id, expected.rule_archetype_id, expected.rule_archetype_name) == (23, 42, 'Burn')


def test_doubled_decks_loads_decks_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = Deck({'id': 17})
    load_decks_by_id = mock.Mock(return_value=[expected])
    monkeypatch.setattr(rule, 'db', lambda: StubDatabase([{
        'deck_id': 17,
        'rule_ids': '23,24',
        'archetype_ids': '42,43',
        'archetype_names': 'Burn|Red Deck Wins',
    }]))
    monkeypatch.setattr(rule.deck, 'load_decks_by_id', load_decks_by_id)

    result = rule.doubled_decks()

    assert result == [expected]
    assert list(load_decks_by_id.call_args.args[0]) == [17]
    assert expected.archetypes_from_rules_names == 'Burn (23), Red Deck Wins (24)'


def test_overlooked_decks_loads_decks_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = Deck({'id': 17})
    load_decks_by_id = mock.Mock(return_value=[expected])
    monkeypatch.setattr(rule, 'db', lambda: StubDatabase([{'deck_id': 17}]))
    monkeypatch.setattr(rule.deck, 'load_decks_by_id', load_decks_by_id)

    result = rule.overlooked_decks()

    assert result == [expected]
    assert list(load_decks_by_id.call_args.args[0]) == [17]


class StubDatabase:
    def __init__(self, rows: list[dict[str, int | str]]) -> None:
        self.rows = rows

    def select(self, _sql: str) -> list[dict[str, int | str]]:
        return self.rows


@pytest.mark.parametrize(
    ('include', 'exclude'),
    [
        ('4 Lightning Bolt\n1 lightning bolt', ''),
        ('', '4 Lightning Bolt\n1 lightning bolt'),
        ('4 Lightning Bolt', '1 lightning bolt'),
    ],
)
def test_update_cards_raw_rejects_duplicate_cards(monkeypatch: pytest.MonkeyPatch, include: str, exclude: str) -> None:
    updates = []
    monkeypatch.setattr(rule.card, 'card_exists', lambda name: True)
    monkeypatch.setattr(rule.oracle, 'valid_name', lambda name: name.title())
    monkeypatch.setattr(rule, 'update_cards', lambda rule_id, inc, exc: updates.append((rule_id, inc, exc)))

    success, message = rule.update_cards_raw(1, include, exclude)

    assert not success
    assert message == 'Card appears more than once in rule: Lightning Bolt'
    assert updates == []


def test_update_cards_raw_updates_distinct_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    updates = []
    monkeypatch.setattr(rule.card, 'card_exists', lambda name: True)
    monkeypatch.setattr(rule.oracle, 'valid_name', lambda name: name.title())
    monkeypatch.setattr(rule, 'update_cards', lambda rule_id, inc, exc: updates.append((rule_id, inc, exc)))

    success, message = rule.update_cards_raw(1, '4 lightning bolt', '1 counterspell')

    assert success
    assert message == ''
    assert updates == [(1, [(4, 'Lightning Bolt')], [(1, 'Counterspell')])]
