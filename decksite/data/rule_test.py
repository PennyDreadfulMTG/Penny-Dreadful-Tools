import pytest

from decksite.data import rule


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
