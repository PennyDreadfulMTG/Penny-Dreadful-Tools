import decksite.data.clauses
from decksite.data import preaggregation, query
from decksite.database import db
from magic import oracle, rotation, seasons
from magic.models import Card
from shared import decorators, logger
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import DatabaseException, OperationalException

# A decksite-level cache of rotation information, primarily to make /rotation much faster.

def load_rotation(where: str = 'TRUE', order_by: str = 'hits', limit: str = '') -> tuple[list[Card], int]:
    sql = f"""
        SELECT
            name,
            hits,
            percent,
            hits_needed,
            percent_needed,
            rank,
            status,
            hit_in_last_run,
            COUNT(*) OVER () AS total
        FROM
            _rotation
        WHERE
            {where}
        ORDER BY
            {order_by}
        {limit}
    """
    try:
        rs = db().select(sql)
        cs = [Container({k: v for k, v in r.items() if k != 'total'}) for r in rs]
    except DatabaseException as e:
        logger.error('Failed to load rotation information', e)
        return [], 0
    cards = oracle.cards_by_name()
    for c in cs:
        c.update(cards[c.name])
    return cs, 0 if not rs else rs[0]['total']

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
def force_cache_update() -> None:
    season_id = seasons.next_season_num()
    db().begin(f'rotation_runs_season_{season_id}')
    # This is why this is so expensive – we start again from scratch every time.
    # This does let us edit the Run_xxx.txt files which happens sometimes when things go wrong.
    db().execute('DELETE FROM rotation_runs WHERE season_id = %s', [season_id])
    update_rotation_runs()
    db().commit(f'rotation_runs_season_{season_id}')
    cache_rotation()

def update_rotation_runs() -> None:
    season_id = seasons.next_season_num()
    for path in rotation.files():
        f = open(path)
        number = rotation.run_number_from_path(path)
        cs = [(number, line.strip()) for line in f.readlines()]
        sql = 'INSERT IGNORE INTO rotation_runs (number, name, season_id) VALUES '
        sql += ', '.join(f'({number}, {sqlescape(name)}, {season_id})' for number, name in cs)
        db().execute(sql)

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
            ROUND(COUNT(*) / @runs_completed * 100) AS percent,
            GREATEST(0, @hits_required - COUNT(*)) AS hits_needed,
            IF(@runs_remaining = 0, 0, ROUND((GREATEST(0, @hits_required - COUNT(*)) / @runs_remaining) * 100)) AS percent_needed,
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
            ({query.ranks_select()}) AS p ON rr.name = p.name
        WHERE
            rr.season_id = @next_season_id
        GROUP BY
            name
    """
    where, msg = decksite.data.clauses.card_search_where('-f:pdall')
    if msg:
        emsg = "Unexpected error generating card search where: '{msg}'"
        logger.error(emsg)
        raise OperationalException(emsg)
    preaggregation.preaggregate(table, sql)
    sql = f'UPDATE _rotation SET rank = 0 WHERE {where}'
    db().execute(sql)
