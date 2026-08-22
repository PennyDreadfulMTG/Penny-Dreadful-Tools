import pytest

from maintenance import deck_hash


def test_recalculate_selected_decks_uses_an_id_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    where: list[str] = []
    cleared: list[str] = []

    def load_decks(**kwargs: str) -> tuple[list[object], int]:
        where.append(kwargs['where'])
        return [], 0

    monkeypatch.setattr(deck_hash.deck, 'load_decks', load_decks)
    monkeypatch.setattr(deck_hash.redis, 'clear', lambda *keys: cleared.extend(keys))

    deck_hash.recalculate({20, 10})

    assert where == ['d.id IN (10, 20)']
    assert set(cleared) == {'decksite:deck:10', 'decksite:deck:20'}
