import datetime
from typing import Any, Dict, List, Optional

from flask import url_for

from decksite.data import archetype, deck, query
from decksite.data.top import Top
from decksite.database import db
from shared import dtutil, guarantee
from shared.container import Container
from shared.database import sqlescape


class Competition(Container):
    def __init__(self, params: Dict[str, Any]) -> None:
        super().__init__(params)
        self.base_archetype_data: Dict[str, int] = {}

    def base_archetypes_data(self) -> Dict[str, int]:
        base_archetype_by_id = archetype.base_archetype_by_id()
        if not self.base_archetype_data:
            self.base_archetype_data = {a.name: 0 for a in archetype.base_archetypes()}
            for d in self.decks:
                if not d.archetype_id:
                    continue
                base_archetype_name = base_archetype_by_id[d.archetype_id].name
                self.base_archetype_data[base_archetype_name] += 1
        return self.base_archetype_data

# pylint: disable=too-many-arguments
def get_or_insert_competition(start_date: datetime.datetime,
                              end_date: datetime.datetime,
                              name: str,
                              competition_series: str,
                              url: Optional[str],
                              top_n: Top) -> int:
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
    db().begin('insert_competition')
    sql = 'INSERT INTO competition (start_date, end_date, name, competition_series_id, url, top_n) VALUES (%s, %s, %s, %s, %s, %s)'
    competition_id = db().insert(sql, [start, end, name, competition_series_id, url, top_n.value])
    if url is None:
        sql = 'UPDATE competition SET url = %s WHERE id = %s'
        db().execute(sql, [url_for('competition', competition_id=competition_id, _external=True), competition_id])
    db().commit('insert_competition')
    return competition_id

def load_competition(competition_id: int) -> Competition:
    return guarantee.exactly_one(load_competitions('c.id = {competition_id}'.format(competition_id=sqlescape(competition_id)), should_load_decks=True))

def load_competitions(where: str = 'TRUE', having: str = 'TRUE', season_id: Optional[int] = None, should_load_decks: Optional[bool] = False) -> List[Competition]:
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
            season.id AS season_id
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
    """.format(season_join=query.season_join(), where=where, season_query=query.season_query(season_id, 'season.id'), having=having)
    competitions = [Competition(r) for r in db().select(sql)]
    for c in competitions:
        c.start_date = dtutil.ts2dt(c.start_date)
        c.end_date = dtutil.ts2dt(c.end_date)
        c.decks = []
    if should_load_decks:
        load_decks(competitions)
    return competitions

def load_decks(competitions: List[Competition]) -> None:
    if competitions == []:
        return
    competitions_by_id = {c.id: c for c in competitions}
    where = 'd.competition_id IN ({ids})'.format(ids=', '.join(str(k) for k in competitions_by_id.keys()))
    decks = deck.load_decks(where)
    for c in competitions:
        c.decks = []
    for d in decks:
        competitions_by_id[d.competition_id].decks.append(d)

def tournaments_with_prizes() -> List[Competition]:
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

def leaderboards(where: str = "ct.name = 'Gatherling'", season_id: Optional[int] = None) -> List[Dict[str, Any]]:
    sql = """
        SELECT
            p.id AS person_id,
            {person_query} AS person,
            cs.name AS competition_series_name,
            sp.name AS sponsor_name,
            COUNT(DISTINCT d.id) AS tournaments,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins,
            COUNT(DISTINCT d.id) + SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS points
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
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            cs.id,
            p.id
        ORDER BY
            cs.id,
            points DESC,
            wins DESC,
            tournaments DESC,
            person
    """.format(person_query=query.person_query(), season_join=query.season_join(), where=where, season_query=query.season_query(season_id, 'season.id'))

    # results is the returned list of leaderboards for each competition
    results = []
    # current holds the currently-being-processed competition before it's added to results
    current: Dict[str, Any] = {}

    for row in db().select(sql):
        k = row['competition_series_name']
        if current.get('competition_series_name', None) != k:
            if len(current) > 0:
                results.append(current)
            current = {
                'competition_series_name': row['competition_series_name'],
                'entries': [],
                'sponsor_name': row['sponsor_name']
            }

        row.pop('competition_series_name')
        c = Container(row)
        c.score = (c.wins, c.points)
        current['entries'].append(c)

    if len(current) > 0:
        results.append(current)
    return results
