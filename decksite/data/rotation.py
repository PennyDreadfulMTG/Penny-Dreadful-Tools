import functools
from collections.abc import Callable
from typing import Any

from decksite.data import preaggregation, query
from decksite.database import db
from magic import oracle, rotation, seasons
from magic.models import Card
from shared import decorators, logger
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import FuncType, T
from shared.pd_exception import DatabaseException, OperationalException

# A decksite-level cache of rotation information, primarily to make /rotation much faster.

# A decorator that skips execution of everything in this module if it's not currently rotation time.
# To test all this stuff set always_show_rotation to True in config.json.
def if_not_in_rotation(val: T) -> Callable[[FuncType[T]], FuncType[T]]:
    def decorator(decorated_func: FuncType[T]) -> FuncType[T]:
        @functools.wraps(decorated_func)
        def wrapper(*args: list[Any], **kwargs: dict[str, Any]) -> T:
            if not rotation.in_rotation():
                return val
            return decorated_func(*args, **kwargs)
        return wrapper
    return decorator

@if_not_in_rotation([])
def load_rotation(where: str = 'TRUE', order_by: str = 'hits', limit: str = '') -> list[Card]:
    sql = f"""
        SELECT
            name,
            hits,
            percent,
            hits_needed,
            percent_needed,
            rank,
            status,
            hit_in_last_run
        FROM
            _rotation
        WHERE
            {where}
        ORDER BY
            {order_by}
        {limit}
    """
    try:
        cs = [Container(r) for r in db().select(sql)]
    except DatabaseException as e:
        logger.error('Failed to load rotation information', e)
        return []
    cards = oracle.cards_by_name()
    for c in cs:
        c.update(cards[c.name])
    return cs

@if_not_in_rotation(0)
def load_rotation_count(where: str = 'TRUE') -> int:
    return db().value(f'SELECT COUNT(*) FROM _rotation WHERE {where}')


@if_not_in_rotation((0, 0))
def load_rotation_summary() -> tuple[int, int]:
    sql = 'SELECT MAX(hits) AS runs, COUNT(*) AS num_cards FROM _rotation'
    try:
        row = db().select(sql)[0]
    except DatabaseException as e:
        logger.error('Unable to get rotation information', e)
        return 0, 0
    return int(row['runs'] or 0), int(row['num_cards'] or 0)

# This is expensive (more than 10s), don't call it on user time.
# To trigger manually without having to be in a python shell, hit /api/rotation/clear_cache in a browser.
@decorators.interprocess_locked('.rotation-cache.lock')
@if_not_in_rotation(None)
def force_cache_update() -> None:
    season_id = seasons.next_season_num()
    db().begin(f'rotation_runs_season_{season_id}')
    # This is why this is so expensive – we start again from scratch every time.
    # This does let us edit the Run_xxx.txt files which happens sometimes when things go wrong.
    db().execute('DELETE FROM rotation_runs WHERE season_id = %s', [season_id])
    update_rotation_runs()
    db().commit(f'rotation_runs_season_{season_id}')
    cache_rotation()

@if_not_in_rotation(None)
def update_rotation_runs() -> None:
    season_id = seasons.next_season_num()
    for path in rotation.files():
        f = open(path)
        number = rotation.run_number_from_path(path)
        cs = [(number, line.strip()) for line in f.readlines()]
        sql = 'INSERT IGNORE INTO rotation_runs (number, name, season_id) VALUES '
        sql += ', '.join(f'({number}, {sqlescape(name)}, {season_id})' for number, name in cs)
        db().execute(sql)

@if_not_in_rotation(None)
def cache_rotation() -> None:
    table = '_rotation'
    sql = f"""
        SET @next_season_id = {seasons.next_season_num()};
        SET @total_runs = {rotation.TOTAL_RUNS};
        SELECT MAX(number) INTO @runs_completed FROM rotation_runs WHERE season_id = @next_season_id;
        SET @runs_remaining = @total_runs - @runs_completed;
        SET @hits_required = @total_runs / 2;
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL PRIMARY KEY,
            hits TINYINT UNSIGNED NOT NULL,
            percent TINYINT UNSIGNED NOT NULL,
            hits_needed TINYINT UNSIGNED NOT NULL,
            percent_needed MEDIUMINT NOT NULL,
            rank INT,
            hit_in_last_run BOOL NOT NULL,
            status VARCHAR(20) NOT NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            rr.name,
            COUNT(*) AS hits,
            ROUND(ROUND(COUNT(*) / @runs_completed, 2) * 100) AS percent,
            GREATEST(0, @hits_required - COUNT(*)) AS hits_needed,
            IF(@remaining_runs = 0, 0, ROUND((GREATEST(0, @hits_required - COUNT(*)) / @runs_remaining) * 100)) AS percent_needed,
            p.rank,
            SUM(IF(number IN (SELECT MAX(number) FROM rotation_runs), 1, 0)) AS hit_in_last_run,
            CASE
                WHEN COUNT(*) >= @hits_required THEN 'Legal'
                WHEN COUNT(*) + @total_runs - (SELECT MAX(number) FROM rotation_runs) >= @hits_required THEN 'Undecided'
                ELSE 'Not Legal'
            END AS status
        FROM
            rotation_runs AS rr
        LEFT JOIN
            ({query.ranks()}) AS p ON rr.name = p.name
        WHERE
            rr.season_id = @next_season_id
        GROUP BY
            name
    """
    where, msg = query.card_search_where('-f:pdall')
    if msg:
        emsg = "Unexpected error generating card search where: '{msg}'"
        logger.error(emsg)
        raise OperationalException(emsg)
    preaggregation.preaggregate(table, sql)
    sql = f'UPDATE _rotation SET rank = 0 WHERE {where}'
    db().execute(sql)
