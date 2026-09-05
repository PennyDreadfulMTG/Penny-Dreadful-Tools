import gzip
import json
from pathlib import Path

import pytest

from magic import card, multiverse
from magic.abc import CardDescription
from magic.database import db


@pytest.mark.functional
def test_base_query_legalities() -> None:
    sql = multiverse.base_query("f.name = 'Mother of Runes'")
    db().execute('SET group_concat_max_len=100000')
    rs = db().select(sql)
    assert len(rs) == 1
    legalities = rs[0]['legalities']
    assert 'Penny Dreadful EMN:Legal' in legalities
    assert 'Penny Dreadful AKH:Legal' not in legalities

def test_supertypes() -> None:
    assert multiverse.supertypes('Legendary Enchantment Creature - God') == ['Legendary']
    assert multiverse.supertypes('Artifact Creature - Construct') == []
    assert multiverse.supertypes('Basic Snow Land - Island') == ['Basic', 'Snow']
    assert multiverse.supertypes('Enchantment') == []
    assert multiverse.supertypes('Creature - Elder Dragon') == []

def test_subtypes() -> None:
    assert multiverse.subtypes('Legendary Enchantment Creature - God') == ['God']
    assert multiverse.subtypes('Artifact Creature - Construct') == ['Construct']
    assert multiverse.subtypes('Basic Snow Land - Island') == ['Island']
    assert multiverse.subtypes('Enchantment') == []
    assert multiverse.subtypes('Creature - Elder Dragon') == ['Elder', 'Dragon']

def test_load_local_cards_supports_compressed_json_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cards: list[CardDescription] = [
        {'name': 'Spider-Man Noir'},
        {'name': 'Peter Parker // Amazing Spider-Man'},
    ]
    with gzip.open(tmp_path / 'scryfall-default-cards.jsonl.gz', 'wt', encoding='utf-8') as f:
        for card in cards:
            f.write(json.dumps(card) + '\n')
    monkeypatch.chdir(tmp_path)
    assert multiverse.load_local_cards() == cards

def test_load_local_oracle_cards_supports_compressed_json_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cards: list[CardDescription] = [
        {'name': 'Forest', 'oracle_id': 'oracle-forest', 'id': 'printing-forest'},
    ]
    with gzip.open(tmp_path / 'scryfall-oracle-cards.jsonl.gz', 'wt', encoding='utf-8') as f:
        for card in cards:
            f.write(json.dumps(card) + '\n')
    monkeypatch.chdir(tmp_path)
    assert multiverse.load_local_oracle_cards() == cards

def test_apply_default_printings_maps_oracle_ids_for_dfc_and_meld() -> None:
    cards = [
        {'id': 1, 'oracle_id': 'oracle-dfc'},
        {'id': 2, 'oracle_id': 'oracle-meld'},
        {'id': 3, 'oracle_id': 'oracle-without-entry'},
    ]
    printings = [
        {'system_id': 'printing-dfc'},
        {'system_id': 'printing-meld'},
        {'system_id': 'another-printing'},
    ]
    oracle_cards: list[CardDescription] = [
        {'oracle_id': 'oracle-dfc', 'id': 'printing-dfc', 'layout': 'transform'},
        {'oracle_id': 'oracle-meld', 'id': 'printing-meld', 'layout': 'meld'},
    ]

    multiverse.apply_default_printings(cards, printings, oracle_cards)

    assert cards == [
        {'id': 1, 'oracle_id': 'oracle-dfc', 'default_printing_system_id': 'printing-dfc'},
        {'id': 2, 'oracle_id': 'oracle-meld', 'default_printing_system_id': 'printing-meld'},
        {'id': 3, 'oracle_id': 'oracle-without-entry', 'default_printing_system_id': None},
    ]

def test_apply_default_printings_rejects_a_printing_we_did_not_import() -> None:
    cards = [{'id': 1, 'oracle_id': 'oracle-id'}]
    oracle_cards: list[CardDescription] = [{'oracle_id': 'oracle-id', 'id': 'filtered-printing'}]

    multiverse.apply_default_printings(cards, [], oracle_cards)

    assert cards[0]['default_printing_system_id'] is None

def test_apply_meld_result_printings_attaches_the_result_id_to_both_fronts() -> None:
    cards = [
        {'id': 1, 'oracle_id': 'oracle-gisela', 'default_printing_system_id': 'printing-gisela'},
        {'id': 2, 'oracle_id': 'oracle-bruna', 'default_printing_system_id': 'printing-bruna'},
        {'id': 3, 'oracle_id': 'oracle-brisela', 'default_printing_system_id': 'printing-brisela'},
    ]
    printings = [
        {'card_id': 1, 'system_id': 'printing-gisela', 'image_status': 'highres_scan'},
        {'card_id': 2, 'system_id': 'printing-bruna', 'image_status': 'highres_scan'},
        {'card_id': 3, 'system_id': 'printing-brisela', 'image_status': 'highres_scan'},
    ]
    meld_result: CardDescription = {
        'name': 'Brisela, Voice of Nightmares',
        'all_parts': [
            {'component': 'meld_part', 'name': 'Gisela, the Broken Blade'},
            {'component': 'meld_part', 'name': 'Bruna, the Fading Light'},
            {'component': 'meld_result', 'name': 'Brisela, Voice of Nightmares'},
        ],
    }
    card_ids = {
        'Gisela, the Broken Blade': 1,
        'Bruna, the Fading Light': 2,
        'Brisela, Voice of Nightmares': 3,
    }

    multiverse.apply_meld_result_printings(cards, printings, [meld_result], card_ids)

    assert cards[0]['meld_result_printing_system_id'] == 'printing-brisela'
    assert cards[1]['meld_result_printing_system_id'] == 'printing-brisela'
    assert cards[2]['meld_result_printing_system_id'] is None

def test_card_aliases_include_english_printed_name() -> None:
    card: CardDescription = {
        'name': 'Spider-Man Noir',
        'printed_name': 'Kroble, Envoy of the Bog',
        'lang': 'en',
    }
    assert multiverse.card_aliases(card) == {'Kroble, Envoy of the Bog'}

def test_card_aliases_include_printed_names_from_faces() -> None:
    card: CardDescription = {
        'name': 'Peter Parker // Amazing Spider-Man',
        'lang': 'en',
        'card_faces': [
            {'name': 'Peter Parker', 'printed_name': 'Surris, Spidersilk Innovator'},
            {'name': 'Amazing Spider-Man', 'printed_name': 'Surris, Silk-Tech Vanguard'},
        ],
    }
    assert multiverse.card_aliases(card) == {
        'Surris, Spidersilk Innovator',
        'Surris, Silk-Tech Vanguard',
        'Surris, Spidersilk Innovator // Surris, Silk-Tech Vanguard',
    }

def test_card_aliases_exclude_non_english_printed_names() -> None:
    card: CardDescription = {
        'name': 'Spider-Man Noir',
        'printed_name': 'Localized Spider-Man Noir',
        'lang': 'fr',
    }
    assert multiverse.card_aliases(card) == set()

def test_canonical_name_matches_stored_double_faced_card_name() -> None:
    card: CardDescription = {
        'name': 'Peter Parker // Amazing Spider-Man',
        'layout': 'transform',
        'card_faces': [
            {'name': 'Peter Parker'},
            {'name': 'Amazing Spider-Man'},
        ],
    }
    assert multiverse.canonical_name(card) == 'Peter Parker'

def test_add_aliases_ignores_ambiguous_aliases() -> None:
    aliases = {'Shared Name': 1}
    ambiguous_aliases: set[str] = set()
    card: CardDescription = {'name': 'Another Card', 'flavor_name': 'Shared Name'}
    multiverse.add_aliases(card, 2, aliases, ambiguous_aliases)
    assert aliases == {}
    assert ambiguous_aliases == {'Shared Name'}

    multiverse.add_aliases({'name': 'Third Card', 'flavor_name': 'Shared Name'}, 3, aliases, ambiguous_aliases)
    assert aliases == {}

def test_insert_many_batches_large_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    queries = []

    class FakeDatabase:
        def execute(self, query: str) -> None:
            queries.append(query)

    database = FakeDatabase()
    monkeypatch.setattr(multiverse, 'db', lambda: database)
    monkeypatch.setattr(multiverse, 'INSERT_BATCH_SIZE', 2)
    values = [
        {'card_id': 1, 'flavor_name': 'One'},
        {'card_id': 2, 'flavor_name': 'Two'},
        {'card_id': 3, 'flavor_name': 'Three'},
    ]

    multiverse.insert_many('card_flavor_name', card.card_flavor_name_properties(), values)

    assert len(queries) == 2
    assert "(1, 'One'), (2, 'Two')" in queries[0]
    assert "(3, 'Three')" in queries[1]

@pytest.mark.asyncio
async def test_alias_from_later_printing_is_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def select(self, query: str) -> list[dict[str, object]]:
            if 'FROM rarity' in query:
                return [
                    {'id': 1, 'name': 'Common'},
                    {'id': 2, 'name': 'Uncommon'},
                    {'id': 3, 'name': 'Rare'},
                    {'id': 4, 'name': 'Mythic Rare'},
                ]
            return []

    monkeypatch.setattr(multiverse, 'db', FakeDatabase)
    monkeypatch.setattr(multiverse, 'load_sets', lambda: {'spm': 1, 'om1': 2})
    printing: CardDescription = {
        'id': '00000000-0000-0000-0000-000000000001',
        'name': 'Spider-Man Noir',
        'oracle_id': '00000000-0000-0000-0000-000000000002',
        'layout': 'normal',
        'type_line': 'Legendary Creature — Spider Hero',
        'rarity': 'rare',
        'set': 'spm',
        'mana_cost': '{2}{B}',
        'cmc': 3,
        'colors': [],
        'color_identity': [],
        'legalities': {},
    }
    omenpaths_printing: CardDescription = printing | {
        'id': '00000000-0000-0000-0000-000000000003',
        'set': 'om1',
        'lang': 'en',
        'printed_name': 'Kroble, Envoy of the Bog',
    }

    values = await multiverse.determine_values_async([printing, omenpaths_printing], 100)

    assert values['flavor_name'] == [{'card_id': 100, 'flavor_name': 'Kroble, Envoy of the Bog'}]
