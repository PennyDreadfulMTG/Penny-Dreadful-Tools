import pytest

from decksite.database import db
from decksite.testutil import with_test_db
from maintenance import canonicalize_card_names

ALIASES = {
    'Rhilex the Accursed': 'Agent Venom',
    'Agent of the Iron Spider': 'Agent Venom',
}


def _insert_deck(identifier: str, featured_card: str | None = None) -> int:
    person_id = db().insert('INSERT INTO person (name, mtgo_username) VALUES (%s, %s)', [identifier, identifier])
    source_id = db().value("SELECT id FROM source WHERE name = 'Tapped Out'")
    return db().insert(
        '''
            INSERT INTO deck (person_id, source_id, identifier, name, created_date, updated_date, featured_card)
            VALUES (%s, %s, %s, %s, 1, 1, %s)
        ''',
        [person_id, source_id, identifier, identifier, featured_card],
    )


@with_test_db
@pytest.mark.functional
def test_audit_and_apply_are_collision_safe_backed_up_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    deck_id = _insert_deck('alias-migration', 'Rhilex the Accursed')
    cards = [
        ('Rhilex the Accursed', 2, 0),
        ('Agent Venom', 1, 0),
        ('Agent of the Iron Spider', 3, 0),
        ('Rhilex the Accursed', 1, 1),
        ('A Future Card', 4, 0),
    ]
    for name, n, sideboard in cards:
        db().execute('INSERT INTO deck_card (deck_id, card, n, sideboard) VALUES (%s, %s, %s, %s)', [deck_id, name, n, sideboard])

    rule_id = db().insert('INSERT INTO rule (archetype_id) VALUES (1)')
    for name, include in [('Rhilex the Accursed', 1), ('Agent Venom', 1), ('Agent of the Iron Spider', 0)]:
        db().execute('INSERT INTO rule_card (rule_id, card, include, n) VALUES (%s, %s, %s, 1)', [rule_id, name, include])

    for number, name in [(1, 'Rhilex the Accursed'), (1, 'Agent Venom'), (2, 'Agent of the Iron Spider')]:
        db().execute('INSERT INTO rotation_runs (number, name, season_id) VALUES (%s, %s, 99)', [number, name])

    monkeypatch.setattr(canonicalize_card_names, 'aliases_from_oracle', lambda: ALIASES)
    recalculated: list[set[int]] = []
    monkeypatch.setattr(canonicalize_card_names.deck_hash, 'recalculate', lambda ids: recalculated.append(ids))
    monkeypatch.setattr(canonicalize_card_names.rotation, 'clear_redis', lambda clear_files=False: None)
    cache_updates: list[bool] = []
    monkeypatch.setattr(canonicalize_card_names.rotation_data, 'cache_rotation', lambda: cache_updates.append(True))

    audit = canonicalize_card_names.audit()

    assert audit.deck_alias_rows == 3
    assert audit.deck_collisions == 2
    assert audit.rule_alias_rows == 2
    assert audit.rule_collisions == 1
    assert audit.rotation_alias_rows == 2
    assert audit.rotation_collisions == 1
    assert db().value(
        'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name LIKE %s',
        [canonicalize_card_names.BACKUP_PREFIX + '%'],
    ) == 0

    canonicalize_card_names.apply()

    assert list(db().select('SELECT card, n, sideboard FROM deck_card WHERE deck_id = %s ORDER BY sideboard, card', [deck_id])) == [
        {'card': 'A Future Card', 'n': 4, 'sideboard': 0},
        {'card': 'Agent Venom', 'n': 6, 'sideboard': 0},
        {'card': 'Agent Venom', 'n': 1, 'sideboard': 1},
    ]
    assert db().value('SELECT featured_card FROM deck WHERE id = %s', [deck_id]) == 'Agent Venom'
    assert list(db().select('SELECT card, include FROM rule_card WHERE rule_id = %s ORDER BY include DESC', [rule_id])) == [
        {'card': 'Agent Venom', 'include': 1},
        {'card': 'Agent Venom', 'include': 0},
    ]
    assert list(db().select('SELECT number, name, season_id FROM rotation_runs ORDER BY number')) == [
        {'number': 1, 'name': 'Agent Venom', 'season_id': 99},
        {'number': 2, 'name': 'Agent Venom', 'season_id': 99},
    ]
    assert db().value(f'SELECT COUNT(*) FROM {canonicalize_card_names.BACKUP_PREFIX}deck_card') == 5
    assert recalculated == [{deck_id}]
    assert cache_updates == [True]

    second_plan = canonicalize_card_names.apply()

    assert second_plan.deck_alias_rows == 0
    assert second_plan.rule_alias_rows == 0
    assert second_plan.rotation_alias_rows == 0
    assert db().value(f'SELECT COUNT(*) FROM {canonicalize_card_names.BACKUP_PREFIX}deck_card') == 5
    assert recalculated == [{deck_id}, {deck_id}]
    assert cache_updates == [True]
