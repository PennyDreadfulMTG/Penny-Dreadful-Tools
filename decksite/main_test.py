import contextlib

import pytest

from decksite import main
from decksite.data import archetype
from decksite.data.archetype import Archetype
from decksite.database import db
from decksite.testutil import with_test_db
from magic.models import Card


class _Done(Exception):
    """Raised to stop home() once we have the archetype list; rendering the page is not what is under test."""


def test_image_route_applies_requested_printing_without_mutating_cached_card(monkeypatch: pytest.MonkeyPatch) -> None:
    cached_card = Card({'name': 'Agent Venom'})
    captured = []
    monkeypatch.setattr(main.oracle, 'load_cards', lambda _names: [cached_card])

    def download_image(cards: list[Card]) -> str:
        captured.extend(cards)
        return 'LICENSE.md'

    monkeypatch.setattr(main.image_fetcher, 'download_image', download_image)

    with main.APP.test_request_context('/image/Agent%20Venom/?printing=om1&printing_id=d62cf4f8-36a2-4d9f-9d52-53ea18a52760'):
        response = main.image('Agent Venom')

    assert response.status_code == 200
    assert captured[0] is not cached_card
    assert captured[0].preferred_printing == 'om1'
    assert captured[0].preferred_printing_system_id == 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'
    assert cached_card.get('preferred_printing') is None
    assert cached_card.get('preferred_printing_system_id') is None


@with_test_db
@pytest.mark.functional
def test_home_page_asks_for_disjoint_archetypes(monkeypatch: pytest.MonkeyPatch) -> None:
    """#15109 called load_archetypes, which rolls a child's decks up into its parent.

    That put the taxonomy roots (Aggro, Control, ...) at the top of the home page's Top Archetypes
    table and counted every deck once per ancestor. Pin the loader the page actually uses.
    """
    db().execute("DELETE FROM archetype_closure")
    db().execute("DELETE FROM archetype")
    db().execute("INSERT INTO archetype (id, name, description) VALUES (1, 'Aggro', ''), (2, 'Red Deck Wins', '')")
    db().execute("INSERT INTO archetype_closure (ancestor, descendant, depth) VALUES (1, 1, 0), (2, 2, 0), (1, 2, 1)")
    archetype.preaggregate_disjoint_archetypes()
    archetype.preaggregate_archetypes()
    for table in ('_arch_disjoint_stats', '_arch_stats'):
        db().execute(f"""
            INSERT INTO {table}
                (archetype_id, season_id, num_decks, wins, losses, draws, perfect_runs, tournament_wins, tournament_top8s, deck_type)
            VALUES (2, 1, 10, 0, 0, 0, 0, 0, 0, 'league')
        """)
    db().execute("""
        INSERT INTO _arch_stats
            (archetype_id, season_id, num_decks, wins, losses, draws, perfect_runs, tournament_wins, tournament_top8s, deck_type)
        VALUES (1, 1, 10, 0, 0, 0, 0, 0, 0, 'league')
    """)

    captured: list[Archetype] = []

    def capture(_news, _decks, _cards, _stats, all_archetypes):  # type: ignore[no-untyped-def]
        captured.extend(all_archetypes)
        raise _Done

    monkeypatch.setattr(main, 'Home', capture)
    monkeypatch.setattr(main, 'get_season_id', lambda: 1)
    # Everything home() loads before the archetypes needs preaggregated tables we do not care about here.
    monkeypatch.setattr(main.ds, 'latest_decks', lambda **_kwargs: [])
    monkeypatch.setattr(main.cs, 'load_cards_with_total', lambda **_kwargs: ([], 0))
    monkeypatch.setattr(main.ns, 'all_news', lambda *_args, **_kwargs: [])

    with main.APP.test_request_context('/'), contextlib.suppress(_Done):
        main.home()

    with_decks = {a.name: a.num_decks for a in captured if a.get('num_decks')}
    assert with_decks == {'Red Deck Wins': 10}, 'Aggro has no decks of its own and must not inherit its child\'s'
