from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from decksite.data import rotation as rotation_data
from decksite.database import db
from magic import oracle, rotation
from maintenance import deck_hash
from shared import redis_wrapper as redis

LOCK_NAME = 'canonicalize_card_names'
TRANSACTION_LABEL = 'canonicalize_card_names'
BACKUP_PREFIX = '_canonicalize_card_names_backup_'


@dataclass
class MigrationPlan:
    aliases: dict[str, str]
    deck_groups: dict[tuple[int, int, str], list[dict[str, Any]]]
    featured_rows: list[dict[str, Any]]
    rule_groups: dict[tuple[int, int, int, int | None, str], list[dict[str, Any]]]
    rotation_groups: dict[tuple[int, int, str], list[dict[str, Any]]]

    @property
    def affected_deck_ids(self) -> set[int]:
        ids = {key[0] for key in self.deck_groups}
        ids.update(row['id'] for row in self.featured_rows)
        return ids

    @property
    def deck_alias_rows(self) -> int:
        return sum(name in self.aliases for rows in self.deck_groups.values() for name in [row['card'] for row in rows])

    @property
    def deck_collisions(self) -> int:
        return sum(len(rows) - 1 for rows in self.deck_groups.values())

    @property
    def rule_alias_rows(self) -> int:
        return sum(name in self.aliases for rows in self.rule_groups.values() for name in [row['card'] for row in rows])

    @property
    def rule_collisions(self) -> int:
        return sum(len(rows) - 1 for rows in self.rule_groups.values())

    @property
    def rotation_alias_rows(self) -> int:
        return sum(name in self.aliases for rows in self.rotation_groups.values() for name in [row['name'] for row in rows])

    @property
    def rotation_collisions(self) -> int:
        return sum(len(rows) - 1 for rows in self.rotation_groups.values())


def aliases_from_oracle() -> dict[str, str]:
    return {
        name: card.name
        for name, card in oracle.cards_by_name().items()
        if name != card.name
    }


def _in_clause(values: Collection[Any]) -> str:
    return ', '.join(['%s'] * len(values))


def _indexed_exact_in(column: str, values: Collection[Any]) -> tuple[str, list[Any]]:
    candidates = list(values)
    placeholders = _in_clause(candidates)
    # The first predicate lets a normal collation index find a candidate superset;
    # the second retains the migration's exact, case-sensitive matching semantics.
    return (
        f'{column} IN ({placeholders}) AND BINARY {column} IN ({placeholders})',
        candidates + candidates,
    )


def _select_alias_rows(table: str, column: str, columns: str, aliases: dict[str, str]) -> list[dict[str, Any]]:
    if not aliases:
        return []
    predicate, args = _indexed_exact_in(column, aliases)
    sql = f'SELECT {columns} FROM {table} WHERE {predicate}'
    return db().select(sql, args)


def _deck_groups(aliases: dict[str, str]) -> dict[tuple[int, int, str], list[dict[str, Any]]]:
    alias_rows = _select_alias_rows('deck_card', 'card', 'id, deck_id, card, n, sideboard', aliases)
    affected_keys = {(row['deck_id'], row['sideboard'], aliases[row['card']]) for row in alias_rows}
    if not affected_keys:
        return {}
    deck_ids = {key[0] for key in affected_keys}
    rows = db().select(
        f'SELECT id, deck_id, card, n, sideboard FROM deck_card WHERE deck_id IN ({_in_clause(deck_ids)})',
        list(deck_ids),
    )
    groups: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        canonical = aliases.get(row['card'], row['card'])
        key = (row['deck_id'], row['sideboard'], canonical)
        if key in affected_keys:
            groups[key].append(row)
    return dict(groups)


def _rule_groups(aliases: dict[str, str]) -> dict[tuple[int, int, int, int | None, str], list[dict[str, Any]]]:
    alias_rows = _select_alias_rows('rule_card', 'card', 'id, rule_id, card, include, n, sideboard', aliases)
    affected_keys = {(row['rule_id'], row['include'], row['n'], row['sideboard'], aliases[row['card']]) for row in alias_rows}
    if not affected_keys:
        return {}
    rule_ids = {key[0] for key in affected_keys}
    rows = db().select(
        f'SELECT id, rule_id, card, include, n, sideboard FROM rule_card WHERE rule_id IN ({_in_clause(rule_ids)})',
        list(rule_ids),
    )
    groups: dict[tuple[int, int, int, int | None, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        canonical = aliases.get(row['card'], row['card'])
        key = (row['rule_id'], row['include'], row['n'], row['sideboard'], canonical)
        if key in affected_keys:
            groups[key].append(row)
    return dict(groups)


def _rotation_groups(aliases: dict[str, str]) -> dict[tuple[int, int, str], list[dict[str, Any]]]:
    alias_rows = _select_alias_rows('rotation_runs', 'name', 'number, name, season_id', aliases)
    affected_keys = {(row['number'], row['season_id'], aliases[row['name']]) for row in alias_rows}
    if not affected_keys:
        return {}
    relevant_names = set(aliases).union(aliases.values())
    predicate, args = _indexed_exact_in('name', relevant_names)
    rows = db().select(
        f'SELECT number, name, season_id FROM rotation_runs WHERE {predicate}',
        args,
    )
    groups: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        canonical = aliases.get(row['name'], row['name'])
        key = (row['number'], row['season_id'], canonical)
        if key in affected_keys:
            groups[key].append(row)
    return dict(groups)


def plan() -> MigrationPlan:
    aliases = aliases_from_oracle()
    return MigrationPlan(
        aliases=aliases,
        deck_groups=_deck_groups(aliases),
        featured_rows=_select_alias_rows('deck', 'featured_card', 'id, featured_card', aliases),
        rule_groups=_rule_groups(aliases),
        rotation_groups=_rotation_groups(aliases),
    )


def print_plan(migration: MigrationPlan, heading: str) -> None:
    print(heading)
    print(f'  Oracle aliases: {len(migration.aliases)}')
    print(f'  deck_card: {migration.deck_alias_rows} alias rows in {len(migration.deck_groups)} card slots across {len({key[0] for key in migration.deck_groups})} decks; {migration.deck_collisions} rows will be merged')
    print(f'  deck.featured_card: {len(migration.featured_rows)} alias rows')
    print(f'  rule_card: {migration.rule_alias_rows} alias rows; {migration.rule_collisions} rows will be merged')
    print(f'  rotation_runs: {migration.rotation_alias_rows} alias rows; {migration.rotation_collisions} rows will be merged')


def audit() -> MigrationPlan:
    migration = plan()
    print_plan(migration, 'Card-name canonicalization dry run (no writes):')
    return migration


def _create_backups(migration: MigrationPlan) -> None:
    database = db()
    for table in ['deck', 'deck_card', 'rule_card', 'rotation_runs']:
        database.execute(f'CREATE TABLE IF NOT EXISTS {BACKUP_PREFIX}{table} LIKE {table}')
    database.execute(f'''
        CREATE TABLE IF NOT EXISTS {BACKUP_PREFIX}mapping (
            alias VARCHAR(190) NOT NULL PRIMARY KEY,
            canonical VARCHAR(190) NOT NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin
    ''')
    for alias, canonical in migration.aliases.items():
        database.execute(
            f'INSERT IGNORE INTO {BACKUP_PREFIX}mapping (alias, canonical) VALUES (%s, %s)',
            [alias, canonical],
        )

    deck_ids = migration.affected_deck_ids
    if deck_ids:
        placeholders = _in_clause(deck_ids)
        args = list(deck_ids)
        database.execute(f'INSERT IGNORE INTO {BACKUP_PREFIX}deck SELECT * FROM deck WHERE id IN ({placeholders})', args)
        database.execute(f'INSERT IGNORE INTO {BACKUP_PREFIX}deck_card SELECT * FROM deck_card WHERE deck_id IN ({placeholders})', args)

    rule_ids = {key[0] for key in migration.rule_groups}
    if rule_ids:
        database.execute(
            f'INSERT IGNORE INTO {BACKUP_PREFIX}rule_card SELECT * FROM rule_card WHERE rule_id IN ({_in_clause(rule_ids)})',
            list(rule_ids),
        )

    if migration.rotation_groups:
        names = set(migration.aliases).union(migration.aliases.values())
        predicate, args = _indexed_exact_in('name', names)
        database.execute(
            f'INSERT IGNORE INTO {BACKUP_PREFIX}rotation_runs SELECT * FROM rotation_runs WHERE {predicate}',
            args,
        )


def _apply_deck_groups(groups: dict[tuple[int, int, str], list[dict[str, Any]]]) -> None:
    for (_deck_id, _sideboard, canonical), rows in groups.items():
        rows.sort(key=lambda row: row['id'])
        keeper, *duplicates = rows
        for row in duplicates:
            db().execute('DELETE FROM deck_card WHERE id = %s', [row['id']])
        db().execute(
            'UPDATE deck_card SET card = %s, n = %s WHERE id = %s',
            [canonical, sum(row['n'] for row in rows), keeper['id']],
        )


def _apply_rule_groups(groups: dict[tuple[int, int, int, int | None, str], list[dict[str, Any]]]) -> None:
    for (_rule_id, _include, _n, _sideboard, canonical), rows in groups.items():
        rows.sort(key=lambda row: row['id'])
        keeper, *duplicates = rows
        for row in duplicates:
            db().execute('DELETE FROM rule_card WHERE id = %s', [row['id']])
        db().execute('UPDATE rule_card SET card = %s WHERE id = %s', [canonical, keeper['id']])


def _apply_rotation_groups(groups: dict[tuple[int, int, str], list[dict[str, Any]]]) -> None:
    aliases = {
        row['name']: canonical
        for (_number, _season_id, canonical), rows in groups.items()
        for row in rows
        if row['name'] != canonical
    }
    for alias, canonical in aliases.items():
        db().execute(
            '''
                INSERT IGNORE INTO rotation_runs (number, name, season_id)
                SELECT number, %s, season_id FROM rotation_runs
                WHERE name = %s AND BINARY name = BINARY %s
            ''',
            [canonical, alias, alias],
        )
        db().execute(
            'DELETE FROM rotation_runs WHERE name = %s AND BINARY name = BINARY %s',
            [alias, alias],
        )


def _backup_deck_ids() -> set[int]:
    return set(db().values(f'SELECT id FROM {BACKUP_PREFIX}deck'))


def apply() -> MigrationPlan:
    database = db()
    database.get_lock(LOCK_NAME, 60)
    try:
        migration = plan()
        print_plan(migration, 'Card-name canonicalization apply plan:')
        _create_backups(migration)
        database.begin(TRANSACTION_LABEL)
        try:
            _apply_deck_groups(migration.deck_groups)
            for row in migration.featured_rows:
                database.execute(
                    'UPDATE deck SET featured_card = %s WHERE id = %s',
                    [migration.aliases[row['featured_card']], row['id']],
                )
            _apply_rule_groups(migration.rule_groups)
            _apply_rotation_groups(migration.rotation_groups)
            database.commit(TRANSACTION_LABEL)
        except Exception:
            database.rollback(TRANSACTION_LABEL)
            raise

        affected_deck_ids = _backup_deck_ids()
        if affected_deck_ids:
            deck_hash.recalculate(affected_deck_ids)
        if migration.rotation_groups:
            rotation.clear_redis(clear_files=True)
            rotation_data.cache_rotation()
        redis.clear(*redis.keys('decksite:deck:*:similar'))
        print('Card-name canonicalization complete. Backup tables use prefix '
              f'{BACKUP_PREFIX}. Run `python run.py maintenance reprime_cache` after deployment.')
        return migration
    finally:
        database.release_lock(LOCK_NAME)


def run() -> None:
    apply()
