from unittest import mock

import pytest

from decksite.data import clauses, deck
from decksite.database import db
from decksite.testutil import with_test_db
from magic import decklist, oracle
from magic.models import Card, Deck
from shared.container import Container


def test_maybe_regenerate_symbols_font_for_unusual_character() -> None:
    with (
        mock.patch.object(deck, 'db') as db,
        mock.patch.object(deck.fonts, 'regenerate_symbols_font') as regenerate_symbols_font,
    ):
        deck.maybe_regenerate_symbols_font('Sparkles ✨')

    db.return_value.get_lock.assert_called_once_with('font_generation', 60 * 15)
    regenerate_symbols_font.assert_called_once_with()
    db.return_value.release_lock.assert_called_once_with('font_generation')


def test_maybe_regenerate_symbols_font_ignores_latin_1() -> None:
    with (
        mock.patch.object(deck, 'db') as db,
        mock.patch.object(deck.fonts, 'regenerate_symbols_font') as regenerate_symbols_font,
    ):
        deck.maybe_regenerate_symbols_font('Déjà Vu')

    db.assert_not_called()
    regenerate_symbols_font.assert_not_called()


def test_set_colors() -> None:
    def card(name: str, mana_cost: str, oracle_text: str = '') -> Card:
        return Card({
            'name': name,
            'mana_cost': mana_cost,
            'oracle_text': oracle_text,
        })

    bop = card('Birds of Paradise', '{G}')
    bbe = card('Bloodbraid Elf', '{2}{R}{G}')
    life_death = card('Life // Death', '{G}|{1}{B}')
    rav_trap = card('Ravenous Trap', '{2}{B}{B}', oracle_text="If an opponent had three or more cards put into their graveyard from anywhere this turn, you may pay {0} rather than pay this spell's mana cost.")
    valentin = card('Valentin, Dean of the Vein', '{B}|{2}{G}{G}')
    finks = card('Kitchen Finks', '{1}{G/W}{G/W}')
    tests = [
        ([], []),
        ([bop], ['G']),
        ([bbe], ['R', 'G']),
        # split should be ignored
        ([bop, bbe, life_death], ['R', 'G']),
        # ravenous trap should be ignored
        ([bop, bbe, rav_trap], ['R', 'G']),
        # modal_dfc should be ignored
        ([bop, bbe, valentin], ['R', 'G']),
        # hybrid should be ignored
        ([bop, bbe, valentin, finks], ['R', 'G']),
    ]
    for cs, output in tests:
        d = Deck({'maindeck': [Container({'card': c, 'n': 4}) for c in cs], 'sideboard': []})
        deck.set_colors(d)
        assert d.colors == output

def test_equivalent_names_have_the_same_deck_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    aliases = {
        'Spider-Man Noir': 'Spider-Man Noir',
        'Kroble, Envoy of the Bog': 'Spider-Man Noir',
    }
    monkeypatch.setattr(oracle, 'valid_name', aliases.__getitem__)
    spider_man = {'maindeck': {'Spider-Man Noir': 4}, 'sideboard': {}}
    omenpaths = {'maindeck': {'Kroble, Envoy of the Bog': 4}, 'sideboard': {}}
    assert deck.get_deckhash(decklist.normalize(spider_man)) == deck.get_deckhash(decklist.normalize(omenpaths))

@with_test_db
@pytest.mark.functional
def test_equivalent_names_are_stored_and_found_as_one_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deck, 'prime_cache', lambda _deck: None)
    common: deck.RawDeckDescription = {
        'name': 'Alias integration test',
        'url': 'https://example.com/deck',
        'source': 'League',
        'mtgo_username': 'AliasTester',
    }
    omenpaths_params: deck.RawDeckDescription = common | {
        'identifier': 'omenpaths-name',
        'cards': {'maindeck': {'Kroble, Envoy of the Bog': 4, 'Swamp': 56}, 'sideboard': {}},
    }
    spiderman_params: deck.RawDeckDescription = common | {
        'identifier': 'spiderman-name',
        'cards': {'maindeck': {'Spider-Man Noir': 4, 'Swamp': 56}, 'sideboard': {}},
    }
    omenpaths = deck.add_deck(omenpaths_params)
    spiderman = deck.add_deck(spiderman_params)

    assert omenpaths.decklist_hash == spiderman.decklist_hash
    stored_cards = db().select('SELECT card, n FROM deck_card WHERE deck_id = %s ORDER BY card', [omenpaths.id])
    assert list(stored_cards) == [
        {'card': 'Spider-Man Noir', 'n': 4},
        {'card': 'Swamp', 'n': 56},
    ]
    matching_ids = db().values(f'SELECT id FROM deck AS d WHERE {clauses.card_where("Kroble, Envoy of the Bog")}')
    assert set(matching_ids) == {omenpaths.id, spiderman.id}
