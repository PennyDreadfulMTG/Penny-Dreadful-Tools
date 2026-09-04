"""
Fixtures for decksite tests.

`seeded_db` points decksite at a small, freshly-built database containing a couple of people,
a tournament, a few decks and matches. It exists so that tests can tell "the page rendered but
showed nothing" apart from "the page works" - a page returning 200 with zero decks is exactly the
kind of failure that a bare smoke test cannot see.

The database is built once per test session (schema + seed data is a few seconds) and only the
configured database name is switched per test, so tests are cheap.
"""
import datetime
from collections.abc import Iterator

import pytest

from decksite.data.top import Top
from shared import configuration, dtutil
from shared.container import Container

SEED_DB_NAME = configuration.get_str('decksite_test_database') + '_seeded'

# Everything in here is deliberately boring and real: real card names (they must exist in the cards db), a real
# competition series, real archetype names from the schema's initial data.
PERSON = 'SmokeTester'
OPPONENT = 'SmokeOpponent'
COMPETITION_NAME = 'Smoke Test Tournament'
COMPETITION_SERIES = 'Penny Dreadful Thursdays'
CARD_IN_TWO_DECKS = 'Lightning Bolt'
CARD_IN_ONE_DECK = 'Counterspell'
ARCHETYPE_WITH_TWO_DECKS = 'Aggro'
ARCHETYPE_WITH_ONE_DECK = 'Control'

DECKS = [
    {'name': 'Smoke Red Aggro', 'identifier': 'smoke-1', 'mtgo_username': PERSON, 'archetype': 'Aggro', 'finish': 1,
     'cards': {'maindeck': {CARD_IN_TWO_DECKS: 4, 'Mountain': 56}, 'sideboard': {}}},
    {'name': 'Smoke Black Aggro', 'identifier': 'smoke-2', 'mtgo_username': PERSON, 'archetype': 'Aggro', 'finish': 2,
     'cards': {'maindeck': {CARD_IN_TWO_DECKS: 4, 'Swamp': 56}, 'sideboard': {}}},
    {'name': 'Smoke Blue Control', 'identifier': 'smoke-3', 'mtgo_username': OPPONENT, 'archetype': 'Control', 'finish': 3,
     'cards': {'maindeck': {CARD_IN_ONE_DECK: 4, 'Island': 56}, 'sideboard': {}}},
]

_seed: Container | None = None


def _build_seed() -> Container:
    from decksite import database
    from decksite.data import archetype, card, competition, deck, match, person
    from decksite.database import db
    from decksite.main import APP
    from maintenance import insert_seasons

    with APP.test_request_context('/'):
        db().execute(f'DROP DATABASE IF EXISTS {SEED_DB_NAME}')
        db().execute(f'CREATE DATABASE {SEED_DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        db().execute(f'USE {SEED_DB_NAME}')
        database.setup()
        insert_seasons.run()
        # A fresh schema has archetypes but no closure rows (prod gets those when archetypes are created through the admin pages) and every archetype query goes through the closure table.
        db().execute('INSERT INTO archetype_closure (ancestor, descendant, depth) SELECT id, id, 0 FROM archetype')  # The schema's season table stops years ago; deck_cache.season_id comes from it, so without this every season-scoped query is empty.

        now = dtutil.now()
        competition_id = competition.get_or_insert_competition(now - datetime.timedelta(days=1), now - datetime.timedelta(hours=20), COMPETITION_NAME, COMPETITION_SERIES, 'https://example.com/smoke-test-tournament', Top.EIGHT)
        decks = []
        for raw in DECKS:
            params: deck.RawDeckDescription = {
                'name': raw['name'],  # type: ignore[typeddict-item]
                'url': f'https://example.com/{raw["identifier"]}',
                'source': 'Gatherling',
                'identifier': raw['identifier'],  # type: ignore[typeddict-item]
                'cards': raw['cards'],  # type: ignore[typeddict-item]
                'archetype': raw['archetype'],  # type: ignore[typeddict-item]
                'mtgo_username': raw['mtgo_username'],  # type: ignore[typeddict-item]
                'competition_id': competition_id,
                'finish': raw['finish'],  # type: ignore[typeddict-item]
            }
            decks.append(deck.add_deck(params))
        match_time = now - datetime.timedelta(hours=22)
        match.insert_match(match_time, decks[0].id, 2, decks[2].id, 1, round_num=1)
        match.insert_match(match_time, decks[1].id, 0, decks[2].id, 2, round_num=1)
        # The site reads most listings from preaggregated tables that a cron job normally rebuilds. Build them now.
        archetype.preaggregate()
        person.preaggregate()
        card.preaggregate()
        deck.preaggregate()

    return Container({
        'db_name': SEED_DB_NAME,
        'person': PERSON,
        'person_id': decks[0].person_id,
        'opponent': OPPONENT,
        'competition_id': competition_id,
        'deck_ids': [d.id for d in decks],
        'num_decks': len(decks),
        'num_people': 2,
        'num_matches': 2,
        'card_in_two_decks': CARD_IN_TWO_DECKS,
        'card_in_one_deck': CARD_IN_ONE_DECK,
        'archetype_with_two_decks': ARCHETYPE_WITH_TWO_DECKS,
        'archetype_with_one_deck': ARCHETYPE_WITH_ONE_DECK,
    })


@pytest.fixture
def seeded_db() -> Iterator[Container]:
    global _seed
    old_db_name = configuration.get_str('decksite_database')
    configuration.CONFIG['decksite_database'] = SEED_DB_NAME
    try:
        if _seed is None:
            _seed = _build_seed()
        yield _seed
    finally:
        configuration.CONFIG['decksite_database'] = old_db_name
