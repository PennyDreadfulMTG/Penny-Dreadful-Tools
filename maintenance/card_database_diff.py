import itertools
import re
from collections.abc import Iterator
from typing import Any

import MySQLdb
from MySQLdb.cursors import SSCursor

from shared import configuration
from shared.pd_exception import InvalidArgumentException

REQUIRES_APP_CONTEXT = False
EXPECTED_OMENPATHS_ALIASES = {
    'Kroble, Envoy of the Bog',
    'Surris, Spidersilk Innovator',
    'Surris, Silk-Tech Vanguard',
}
SPECIAL_TABLES = {'_cache_card', 'card_flavor_name', 'card_legality', 'scryfall_version'}
SURROGATE_ID_TABLES = {
    'card_bug',
    'card_color',
    'card_color_identity',
    'card_produced_mana',
    'card_subtype',
    'card_supertype',
}


def compare(baseline: str, candidate: str) -> bool:
    validate_database_name(baseline)
    validate_database_name(candidate)
    baseline_tables = tables(baseline)
    candidate_tables = tables(candidate)
    if baseline_tables != candidate_tables:
        print(f'Table mismatch: baseline-only={baseline_tables - candidate_tables}, candidate-only={candidate_tables - baseline_tables}')
        return False

    success = True
    for table in sorted(baseline_tables - SPECIAL_TABLES):
        excluded_columns = {'id'} if table in SURROGATE_ID_TABLES else set()
        success = compare_table(baseline, candidate, table, excluded_columns) and success
    success = compare_table(baseline, candidate, '_cache_card', {'flavor_names', 'legalities', 'pd_legal'}) and success
    success = compare_aliases(baseline, candidate) and success
    success = compare_legalities(baseline, candidate) and success
    return success

def validate_database_name(database: str) -> None:
    if not re.fullmatch(r'pd_alias_shadow_[a-z0-9_]+', database):
        raise InvalidArgumentException(f'Shadow database name must start with `pd_alias_shadow_`: {database}')
    if database not in databases():
        raise InvalidArgumentException(f'Shadow database does not exist: {database}')

def connection(database: str = 'information_schema', cursorclass: type = SSCursor) -> Any:
    return MySQLdb.connect(
        host=configuration.mysql_host.value,
        port=configuration.mysql_port.value,
        user=configuration.mysql_user.value,
        passwd=configuration.mysql_passwd.value,
        db=database,
        charset='utf8mb4',
        use_unicode=True,
        cursorclass=cursorclass,
    )

def databases() -> set[str]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT schema_name FROM schemata')
        return {row[0] for row in cursor}

def tables(database: str) -> set[str]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT table_name FROM tables WHERE table_schema = %s', [database])
        return {row[0] for row in cursor}

def columns(database: str, table: str) -> list[str]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT column_name FROM columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position',
            [database, table],
        )
        return [row[0] for row in cursor]

def primary_key(database: str, table: str) -> list[str]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT column_name FROM key_column_usage
               WHERE table_schema = %s AND table_name = %s AND constraint_name = 'PRIMARY'
               ORDER BY ordinal_position""",
            [database, table],
        )
        return [row[0] for row in cursor]

def rows(database: str, table: str, selected_columns: list[str], order_by: list[str]) -> Iterator[tuple[Any, ...]]:
    conn = connection(database)
    cursor = conn.cursor()
    selected = ', '.join(f'`{column}`' for column in selected_columns)
    ordering = ', '.join(f'`{column}`' for column in order_by)
    cursor.execute(f'SELECT {selected} FROM `{table}` ORDER BY {ordering}')
    try:
        yield from cursor
    finally:
        cursor.close()
        conn.close()

def compare_table(baseline: str, candidate: str, table: str, excluded_columns: set[str] | None = None) -> bool:
    excluded_columns = excluded_columns or set()
    baseline_columns = columns(baseline, table)
    candidate_columns = columns(candidate, table)
    if baseline_columns != candidate_columns:
        print(f'{table}: schema differs')
        return False
    selected_columns = [column for column in baseline_columns if column not in excluded_columns]
    order_by = [column for column in primary_key(baseline, table) if column in selected_columns]
    if not order_by:
        order_by = ['card_id'] if 'card_id' in selected_columns else selected_columns
    baseline_rows = rows(baseline, table, selected_columns, order_by)
    candidate_rows = rows(candidate, table, selected_columns, order_by)
    for row_number, (before, after) in enumerate(itertools.zip_longest(baseline_rows, candidate_rows), start=1):
        if before != after:
            print(f'{table}: first difference at row {row_number}: {before!r} != {after!r}')
            return False
    print(f'{table}: identical')
    return True

def aliases(database: str) -> set[tuple[int, str]]:
    with connection(database) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT card_id, flavor_name FROM card_flavor_name')
        return {(row[0], row[1]) for row in cursor}

def compare_aliases(baseline: str, candidate: str) -> bool:
    before = aliases(baseline)
    after = aliases(candidate)
    removed = before - after
    added = after - before
    if removed:
        print(f'card_flavor_name: unexpectedly removed {len(removed)} aliases; sample={sorted(removed)[:10]}')
        return False
    candidate_names = {name for _, name in after}
    missing_examples = EXPECTED_OMENPATHS_ALIASES - candidate_names
    if missing_examples:
        print(f'card_flavor_name: expected new aliases are missing: {sorted(missing_examples)}')
        return False
    if has_ambiguous_aliases(candidate):
        return False
    print(f'card_flavor_name: retained {len(before)} aliases and added {len(added)}; sample={sorted(added)[:10]}')
    return True

def legalities(database: str) -> set[tuple[int, int, str]]:
    with connection(database) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT card_id, format_id, legality FROM card_legality')
        return {(row[0], row[1], row[2]) for row in cursor}

def compare_legalities(baseline: str, candidate: str) -> bool:
    before = legalities(baseline)
    after = legalities(candidate)
    removed = before - after
    added = after - before
    if removed:
        print(f'card_legality: unexpectedly removed {len(removed)} entries; sample={sorted(removed)[:10]}')
        return False
    added_alias_card_ids = {card_id for card_id, _ in aliases(candidate) - aliases(baseline)}
    unrelated = {row for row in added if row[0] not in added_alias_card_ids}
    if unrelated:
        print(f'card_legality: added {len(unrelated)} entries for cards without new aliases; sample={sorted(unrelated)[:10]}')
        return False
    print(
        f'card_legality: retained {len(before)} entries and added {len(added)} entries '
        f'for {len({row[0] for row in added})} cards with newly recognized aliases',
    )
    return True

def has_ambiguous_aliases(database: str) -> bool:
    with connection(database) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT flavor_name, COUNT(DISTINCT card_id)
               FROM card_flavor_name
               GROUP BY flavor_name
               HAVING COUNT(DISTINCT card_id) > 1""",
        )
        ambiguous = list(cursor)
        cursor.execute(
            """SELECT fn.flavor_name, fn.card_id, c.card_id
               FROM card_flavor_name AS fn
               INNER JOIN _cache_card AS c ON c.name = fn.flavor_name AND c.card_id <> fn.card_id""",
        )
        canonical_collisions = list(cursor)
    if ambiguous:
        print(f'card_flavor_name: ambiguous aliases: {ambiguous[:10]}')
    if canonical_collisions:
        print(f'card_flavor_name: canonical-name collisions: {canonical_collisions[:10]}')
    return bool(ambiguous or canonical_collisions)
