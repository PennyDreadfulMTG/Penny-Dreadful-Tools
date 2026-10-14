from collections.abc import Iterator

import pytest

from decksite.data import playability
from decksite.database import db
from shared.container import Container


@pytest.fixture
def legal_cards_table(seeded_db: Container) -> Iterator[None]:
    db().execute('DROP TABLE IF EXISTS _legal_cards')
    try:
        yield
    finally:
        db().execute('DROP TABLE IF EXISTS _legal_cards')


@pytest.mark.functional
def test_legal_cards_refresh_backfills_supplemental_cards(monkeypatch: pytest.MonkeyPatch, legal_cards_table: None) -> None:
    cards_by_season = {'f:pd38': {'Plains'}, 'f:pd37': {'Island'}, 'f:pd39': {'Swamp'}}
    monkeypatch.setattr(playability.search, 'search', lambda query: cards_by_season.get(query, {'Plains'}))

    playability.preaggregate_legal_cards()
    assert set(db().values('SELECT name FROM _legal_cards WHERE season_id = 38')) == {'Plains'}

    # The next full season has already been populated when we repair S38.
    cards_by_season['f:pd38'].update({'Plasma Bolt', 'Monoist Sentry'})
    playability.preaggregate_legal_cards()
    playability.preaggregate_legal_cards()

    assert set(db().values('SELECT name FROM _legal_cards WHERE season_id = 38')) == {'Plains', 'Plasma Bolt', 'Monoist Sentry'}
    assert db().values('SELECT name FROM _legal_cards WHERE season_id = 37') == ['Island']
    assert db().values('SELECT name FROM _legal_cards WHERE season_id = 39') == ['Swamp']
    assert db().value('SELECT COUNT(*) FROM _legal_cards WHERE season_id = 38') == 3


@pytest.mark.functional
@pytest.mark.parametrize('invalid', [False, True])
def test_legal_cards_refresh_preserves_seasons_unavailable_to_search(monkeypatch: pytest.MonkeyPatch, legal_cards_table: None, invalid: bool) -> None:
    monkeypatch.setattr(playability.search, 'search', lambda query: {'Plains'})
    playability.preaggregate_legal_cards()

    def unavailable(query: str) -> set[str]:
        if invalid and query == 'f:pd38':
            raise playability.search.InvalidValueException('Unavailable season')
        return set()

    monkeypatch.setattr(playability.search, 'search', unavailable)
    playability.preaggregate_legal_cards()
    assert db().values('SELECT name FROM _legal_cards WHERE season_id = 38') == ['Plains']


@pytest.mark.functional
def test_legal_cards_refresh_handles_empty_search(monkeypatch: pytest.MonkeyPatch, legal_cards_table: None) -> None:
    monkeypatch.setattr(playability.search, 'search', lambda query: set())

    playability.preaggregate_legal_cards()

    assert db().value('SELECT COUNT(*) FROM _legal_cards') == 0


@pytest.mark.functional
def test_supplemental_refresh_updates_playability_and_archetype_key_cards(monkeypatch: pytest.MonkeyPatch, legal_cards_table: None) -> None:
    season_id = db().value('SELECT season_id FROM deck_cache LIMIT 1')
    legal_cards = {'Plains'}
    monkeypatch.setattr(playability.search, 'search', lambda query: legal_cards if query == f'f:pd{season_id}' else {'Plains'})

    playability.preaggregate()
    assert db().value('SELECT COUNT(*) FROM _season_card_count') == 0

    # These cards already have decks in the seeded season, but become legal
    # after the initial population of its bulk legality cache.
    legal_cards.update({'Lightning Bolt', 'Counterspell'})
    playability.preaggregate()

    assert db().value("SELECT num_decks FROM _season_card_count WHERE season_id = %s AND name = 'Lightning Bolt'", [season_id]) == 2
    assert db().value("SELECT num_decks FROM _season_archetype_card_count WHERE season_id = %s AND name = 'Lightning Bolt'", [season_id]) == 2
    assert playability.playability()['Lightning Bolt'] == pytest.approx(2 / 3, abs=0.00001)
    assert 'Lightning Bolt' in playability.key_cards(season_id).values()
