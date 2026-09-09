from typing import Any

import pytest

from maintenance import guess_league_archetypes
from shared.container import Container


def test_run_assigns_archetype_from_nearest_reviewed_deck(monkeypatch: pytest.MonkeyPatch) -> None:
    similar = Container(id=2, archetype_id=7, reviewed=True)
    source = Container(id=1, archetype_id=None, similar_decks=[similar])
    assignments: list[tuple[Any, ...]] = []

    monkeypatch.setattr(guess_league_archetypes.deck, 'load_decks', lambda *args, **kwargs: [source])
    monkeypatch.setattr(guess_league_archetypes.deck, 'calculate_similar_decks', lambda decks: None)
    monkeypatch.setattr(guess_league_archetypes.deck, 'similarity_score', lambda a, b: 0.92)
    monkeypatch.setattr(guess_league_archetypes.archetype, 'assign', lambda *args: assignments.append(args))

    guess_league_archetypes.run()

    assert assignments == [(1, 7, None, False, 92)]
