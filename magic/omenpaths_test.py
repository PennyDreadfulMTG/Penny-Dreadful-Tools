from pathlib import Path

import pytest
from whoosh.index import create_in

from magic import decklist, legality, oracle, whoosh_write


@pytest.mark.functional
def test_imported_omenpaths_names_resolve_to_spiderman_cards() -> None:
    expected_names = {
        'Kroble, Envoy of the Bog': 'Spider-Man Noir',
        'Surris, Spidersilk Innovator': 'Peter Parker',
        'Surris, Silk-Tech Vanguard': 'Peter Parker',
        'Surris, Spidersilk Innovator // Surris, Silk-Tech Vanguard': 'Peter Parker',
    }
    for omenpaths_name, spiderman_name in expected_names.items():
        assert oracle.valid_name(omenpaths_name) == spiderman_name
        assert oracle.cards_by_name()[omenpaths_name].id == oracle.cards_by_name()[spiderman_name].id

@pytest.mark.functional
def test_mixed_equivalent_names_are_one_deck_entry() -> None:
    raw = {
        'maindeck': {
            'Spider-Man Noir': 2,
            'Kroble, Envoy of the Bog': 2,
            'Swamp': 56,
        },
        'sideboard': {},
    }
    deck = decklist.vivify(raw)
    assert [(entry.name, entry.n) for entry in deck.maindeck if entry.name == 'Spider-Man Noir'] == [('Spider-Man Noir', 4)]
    assert '4 Spider-Man Noir' in str(deck)
    assert 'Kroble, Envoy of the Bog' not in str(deck)

@pytest.mark.functional
def test_equivalent_names_share_the_four_copy_limit() -> None:
    raw = {
        'maindeck': {
            'Spider-Man Noir': 3,
            'Kroble, Envoy of the Bog': 2,
            'Swamp': 55,
        },
        'sideboard': {},
    }
    deck = decklist.vivify(raw)
    errors: dict[str, dict[str, set[str]]] = {}
    assert legality.legal_formats(deck, {'Legacy'}, errors) == set()
    assert errors['Legacy']['Legality_Too_Many'] == {'Spider-Man Noir'}

@pytest.mark.functional
def test_equivalent_names_share_the_four_copy_limit_across_sideboard() -> None:
    raw = {
        'maindeck': {
            'Spider-Man Noir': 3,
            'Swamp': 57,
        },
        'sideboard': {
            'Kroble, Envoy of the Bog': 2,
        },
    }
    deck = decklist.vivify(raw)
    errors: dict[str, dict[str, set[str]]] = {}
    assert legality.legal_formats(deck, {'Legacy'}, errors) == set()
    assert errors['Legacy']['Legality_Too_Many'] == {'Spider-Man Noir'}

@pytest.mark.functional
def test_existing_name_matching_behavior_is_unchanged() -> None:
    assert oracle.valid_name('Godzilla, King of the Monsters') == 'Zilortha, Strength Incarnate'
    assert oracle.valid_name('Far/Away') == 'Far // Away'
    assert oracle.valid_name('Torrent Sculptor // Flamethrower Sonata') == 'Torrent Sculptor'

@pytest.mark.functional
def test_imported_alias_is_written_to_search_index(tmp_path: Path) -> None:
    card = oracle.cards_by_name()['Spider-Man Noir']
    index = create_in(tmp_path, whoosh_write.WhooshWriter().schema)
    whoosh_write.update_index(index, [card])
    with index.reader() as reader:
        documents = [fields for _, fields in reader.iter_docs()]
    assert any(document['name'] == 'Kroble, Envoy of the Bog' and document['canonical_name'] == 'Spider-Man Noir' for document in documents)
