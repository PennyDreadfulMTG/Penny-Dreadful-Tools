import datetime

from decksite.data import preaggregation, query
from decksite.database import db
from shared import dtutil
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import retry_after_calling
from shared.pd_exception import InvalidDataException

SEASONS: list[Container] = []

def get_season_id(dt: datetime.datetime) -> int:
    if len(SEASONS) == 0:
        init_seasons()
    if dt < SEASONS[0].start_date:
        raise InvalidDataException("Can't get a season from {dt} because it is before PD began")
    for s in SEASONS:
        if s.start_date > dt:
            return s.id - 1
    return SEASONS[-1].id

def init_seasons() -> None:
    sql = 'SELECT id, start_date FROM season ORDER BY start_date'
    for r in db().select(sql):
        SEASONS.append(Container({'id': r['id'], 'start_date': dtutil.ts2dt(r['start_date'])}))

def preaggregate() -> None:
    preaggregate_season_stats()

# All of this takes about 8s so let's not do it on user time. Split into multiple queries because it's much faster.
def preaggregate_season_stats() -> None:
    sql = """
        SELECT
            season.season_id,
            season_info.start_date,
            season_info.end_date,
            COUNT(DISTINCT d.id) AS num_decks,
            COUNT(DISTINCT (CASE WHEN ct.name = 'League' THEN d.id ELSE NULL END)) AS num_league_decks,
            COUNT(DISTINCT d.person_id) AS num_people,
            COUNT(DISTINCT c.id) AS num_competitions,
            COUNT(DISTINCT d.archetype_id) AS num_archetypes
        FROM
            deck AS d
        INNER JOIN
            deck_match AS dm ON d.id = dm.deck_id
        {competition_join}
        {season_join}
        LEFT JOIN
        (
            SELECT
                `start`.id,
                `start`.code,
                `start`.start_date AS start_date,
                `end`.start_date AS end_date
            FROM
                season AS `start`
            LEFT JOIN
                season AS `end` ON `end`.id = `start`.id + 1
        ) AS season_info ON season_info.id = season.season_id
        GROUP BY
            season.season_id;
    """.format(competition_join=query.competition_join(), season_join=query.season_join())
    rs = db().select(sql)
    stats = {r['season_id']: r for r in rs}
    sql = """
        SELECT
            season.season_id,
            COUNT(DISTINCT dm.match_id) AS num_matches
        FROM
            deck_match AS dm
        INNER JOIN
            deck AS d ON dm.deck_id = d.id
        {season_join}
        GROUP BY
            season.season_id
    """.format(season_join=query.season_join())
    rs = db().select(sql)
    for r in rs:
        stats.get(r['season_id'], {}).update(r)
    sql = """
        SELECT
            season.season_id,
            COUNT(DISTINCT dc.card) AS num_cards
        FROM
            deck_card AS dc
        INNER JOIN
            deck AS d ON dc.deck_id = d.id
        {season_join}
        GROUP BY
            season.season_id
    """.format(season_join=query.season_join())
    rs = db().select(sql)
    for r in rs:
        stats.get(r['season_id'], {}).update(r)
    table = '_season_stats'
    columns = ['season_id', 'start_date', 'end_date', 'num_decks', 'num_league_decks', 'num_people', 'num_competitions', 'num_archetypes', 'num_matches', 'num_cards']
    values = []
    for season in stats.values():
        values.append('(' + ', '.join(str(sqlescape(season[k])) for k in columns) + ')')
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            season_id INT NOT NULL,
            start_date INT NOT NULL,
            end_date INT,
            num_decks INT NOT NULL,
            num_league_decks INT NOT NULL,
            num_people INT NOT NULL,
            num_competitions INT NOT NULL,
            num_archetypes INT NOT NULL,
            num_matches INT NOT NULL,
            num_cards INT NOT NULL,
            PRIMARY KEY (season_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE
        );
    """.format(table=table)
    preaggregation.preaggregate(table, sql)
    values_s = ', '.join(values)
    db().execute(f'INSERT INTO {table} VALUES {values_s}')

@retry_after_calling(preaggregate_season_stats)
def season_stats() -> dict[int, dict[str, int | datetime.datetime]]:
    sql = """
        SELECT
            season_id,
            start_date,
            end_date,
            DATEDIFF(IFNULL(FROM_UNIXTIME(end_date), NOW()), FROM_UNIXTIME(start_date)) AS length_in_days,
            num_decks,
            num_league_decks,
            num_people,
            num_competitions,
            num_archetypes,
            num_matches,
            num_cards
        FROM
            _season_stats
    """
    stats = {r['season_id']: r for r in db().select(sql)}
    for season in stats.values():
        season['start_date'] = dtutil.ts2dt(season['start_date'])
        season['end_date'] = dtutil.ts2dt(season['end_date']) if season['end_date'] else None
    return stats
