import datetime
from collections.abc import Sequence
from typing import Any

from flask import url_for

from decksite.data import deck, query
from decksite.data.top import Top
from decksite.database import db
from decksite.tournament import CompetitionFlag
from magic.models import Competition
from shared import dtutil, guarantee
from shared.container import Container
from shared.database import sqlescape


def get_or_insert_competition(start_date: datetime.datetime,
                              end_date: datetime.datetime,
                              name: str,
                              competition_series: str,
                              url: str | None,
                              top_n: Top,
                              competition_flag: CompetitionFlag | None = None) -> int:
    competition_series_id = db().value('SELECT id FROM competition_series WHERE name = %s', [competition_series], fail_on_missing=True)
    start = start_date.timestamp()
    end = end_date.timestamp()
    sql = """
        SELECT id
        FROM competition
        WHERE
            name = %s
    """
    competition_id = db().value(sql, [name])
    if competition_id:
        return competition_id
    competition_flag_id = competition_flag.value if competition_flag else None
    db().begin('insert_competition')
    sql = 'INSERT INTO competition (start_date, end_date, name, competition_series_id, url, top_n, competition_flag_id) VALUES (%s, %s, %s, %s, %s, %s, %s)'
    competition_id = db().insert(sql, [start, end, name, competition_series_id, url, top_n.value, competition_flag_id])
    if url is None:
        sql = 'UPDATE competition SET url = %s WHERE id = %s'
        db().execute(sql, [url_for('competition', competition_id=competition_id, _external=True), competition_id])
    db().commit('insert_competition')
    return competition_id

def load_competition(competition_id: int, should_load_decks: bool = True) -> Competition:
    return guarantee.exactly_one(load_competitions(f'c.id = {sqlescape(competition_id)}', should_load_decks=should_load_decks))

def load_competitions(where: str = 'TRUE', having: str = 'TRUE', limit: str = '', season_id: int | None = None, should_load_decks: bool | None = False) -> list[Competition]:
    sql = """
        SELECT
            c.id,
            c.name,
            c.start_date,
            c.end_date,
            c.url,
            c.top_n,
            COUNT(d.id) AS num_decks,
            SUM(CASE WHEN d.reviewed THEN 1 ELSE 0 END) AS num_reviewed,
            sp.name AS sponsor_name,
            cs.name AS series_name,
            ct.name AS type,
            season.season_id
        FROM
            competition AS c
        LEFT JOIN
            deck AS d ON c.id = d.competition_id
        LEFT JOIN
            competition_series AS cs ON cs.id = c.competition_series_id
        LEFT JOIN
            competition_type as ct ON ct.id = cs.competition_type_id
        LEFT JOIN
            sponsor AS sp ON cs.sponsor_id = sp.id
        {season_join}
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            c.id
        HAVING
            {having}
        ORDER BY
            c.start_date DESC,
            c.name
        {limit}
    """.format(season_join=query.season_join(), where=where, season_query=query.season_query(season_id, 'season.season_id'), having=having, limit=limit)
    competitions = [Competition(r) for r in db().select(sql)]
    for c in competitions:
        c.start_date = dtutil.ts2dt(c.start_date)
        c.end_date = dtutil.ts2dt(c.end_date)
        c.decks = []
    if should_load_decks:
        load_decks(competitions)
    return competitions

def load_decks(competitions: list[Competition]) -> None:
    if not competitions:
        return
    competitions_by_id = {c.id: c for c in competitions}
    where = 'd.competition_id IN ({ids})'.format(ids=', '.join(str(k) for k in competitions_by_id.keys()))
    decks, _ = deck.load_decks(where)
    for c in competitions:
        c.decks = []
    for d in decks:
        competitions_by_id[d.competition_id].decks.append(d)

def tournaments_with_prizes() -> list[Competition]:
    where = """
            cs.competition_type_id
        IN
            ({competition_type_id_select})
        AND
            cs.sponsor_id IS NOT NULL
        AND
            c.start_date > (UNIX_TIMESTAMP(NOW() - INTERVAL 26 WEEK))
        """.format(competition_type_id_select=query.competition_type_id_select('Gatherling'))
    return load_competitions(where, should_load_decks=True)

def series(season_id: int | None = None) -> list[dict[str, Any]]:
    competition_join = query.competition_join()
    season_join = query.season_join()
    season_query = query.season_query(season_id, 'season.season_id')
    sql = f"""
        SELECT
            cs.id AS competition_series_id,
            cs.name AS competition_series_name,
            s.name AS sponsor_name
        FROM
            deck AS d
        {competition_join}
        LEFT JOIN
            sponsor AS s ON cs.sponsor_id = s.id
        {season_join}
        WHERE
            ({season_query}) AND (ct.name = 'Gatherling')
        GROUP BY
            cs.id
        ORDER BY
            cs.day_of_week
    """
    return [Container(r) for r in db().select(sql)]

def load_leaderboard(where: str = "ct.name = 'Gatherling'", group_by: str = 'cs.id, p.id', order_by: str = 'cs.id', limit: str = '', season_id: str | int | None = None) -> tuple[Sequence[Container], int]:
    person_query = query.person_query()
    season_join = query.season_join()
    season_query = query.season_query(season_id, 'season.season_id')
    sql = f"""
        SELECT
            p.id AS person_id,
            {person_query} AS person,
            cs.id AS competition_series_id,
            cs.name AS competition_series_name,
            sp.name AS sponsor_name,
            COUNT(DISTINCT d.id) AS num_decks,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins,
            -- Points are complicated because tournaments count entries while leagues do not and leagues count 5-0s but tournaments do not.
            (CASE WHEN ct.name <> 'League' THEN COUNT(DISTINCT d.id) ELSE 0 END) + SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) + COUNT(DISTINCT CASE WHEN five_ohs.five_oh AND ct.name = 'League' THEN d.id ELSE NULL END) AS points,
            ROW_NUMBER() OVER (ORDER BY points DESC, wins DESC, person) AS finish,
            season.season_id,
            COUNT(*) OVER () AS total
        FROM
            competition AS c
        INNER JOIN
            competition_series AS cs ON cs.id = c.competition_series_id
        LEFT JOIN
            sponsor AS sp ON sp.id = cs.sponsor_id
        INNER JOIN
            competition_type AS ct ON ct.id = cs.competition_type_id
        INNER JOIN
            deck AS d ON d.competition_id = c.id
        INNER JOIN
            person AS p ON d.person_id = p.id
        LEFT JOIN
            deck_match AS dm ON dm.deck_id = d.id
        LEFT JOIN
            deck_match AS odm ON odm.match_id = dm.match_id AND odm.deck_id <> d.id
        {season_join}
        -- Make a special join table so we can know if each deck 5-0'ed or not. Note this doesn't check that it's a League run that's done in the SELECT.
        LEFT JOIN
            (
                SELECT
                    d.id AS deck_id,
                    (CASE WHEN cache.wins >= 5 AND cache.losses = 0 THEN 1 ELSE 0 END) AS five_oh
                FROM
                    deck AS d
                INNER JOIN
                    deck_cache AS cache ON d.id = cache.deck_id
            ) AS five_ohs ON d.id = five_ohs.deck_id
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            {group_by}
        ORDER BY
            {order_by},
            points DESC,
            wins DESC,
            num_decks DESC,
            person
        {limit}
    """
    rs = db().select(sql)
    entries = [Container({k: v for k, v in r.items() if k != 'total'}) for r in rs]
    return entries, 0 if not rs else rs[0]['total']

def set_doorprize(competition_name: str, winner: str) -> None:
    sql = """
        INSERT INTO doorprize (competition_name, winner_name)
        VALUES (%s, %s)
        """
    db().execute(sql, [competition_name, winner])
