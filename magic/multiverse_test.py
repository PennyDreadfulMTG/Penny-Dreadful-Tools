import gzip
import json
from pathlib import Path

import pytest

from magic import multiverse
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
