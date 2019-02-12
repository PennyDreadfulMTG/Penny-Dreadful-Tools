import datetime
from typing import Dict, List, Optional

from flask import url_for

from decksite.data import deck, elo, query
from decksite.database import db
from magic import rotation
from magic.models import Deck
from shared import dtutil, redis
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException


# pylint: disable=too-many-arguments
def insert_match(dt: datetime.datetime,
                 left_id: int,
                 left_games: int,
                 right_id: int,
                 right_games: int,
                 round_num: Optional[int] = None,
                 elimination: Optional[int] = None,
                 mtgo_match_id: Optional[int] = None) -> int:
    if left_games == right_games:
        raise InvalidDataException('`insert_match` does not support draws.')
    winner_id = left_id if left_games > right_games else right_id
    loser_id = left_id if left_games < right_games else right_id
    db().begin('insert_match')
    match_id = db().insert('INSERT INTO `match` (`date`, `round`, elimination, mtgo_id) VALUES (%s, %s, %s, %s)', [dtutil.dt2ts(dt), round_num, elimination, mtgo_match_id])
    sql = 'UPDATE deck_cache SET wins = IFNULL(wins, 0) + 1, active_date = %s WHERE deck_id = %s'
    db().execute(sql, [dtutil.dt2ts(dt), winner_id])
    sql = 'UPDATE deck_cache SET losses = IFNULL(losses, 0) + 1, active_date = %s WHERE deck_id = %s'
    db().execute(sql, [dtutil.dt2ts(dt), loser_id])
    sql = 'INSERT INTO deck_match (deck_id, match_id, games) VALUES (%s, %s, %s)'
    db().execute(sql, [left_id, match_id, left_games])
    if right_id is not None: # Don't insert matches or adjust Elo for the bye.
        db().execute(sql, [right_id, match_id, right_games])
        elo.adjust_elo(winner_id, loser_id)
    db().commit('insert_match')
    redis.clear(f'decksite:deck:{left_id}')
    if right_id is not None:
        redis.clear(f'decksite:deck:{right_id}')
    return match_id

# BAKERT unify with load_matches, probably?
def get_matches(d: deck.Deck, should_load_decks: bool = False) -> List[Container]:
    sql = """
        SELECT
            m.`date`,
            m.id,
            m.`round`,
            m.elimination,
            d1.id AS deck_id,
            dm1.games AS game_wins,
            dm2.deck_id AS opponent_deck_id,
            IFNULL(dm2.games, 0) AS game_losses,
            d2.name AS opponent_deck_name,
            {person_query} AS opponent
        FROM
            `match` AS m
        INNER JOIN
            deck_match AS dm1 ON m.id = dm1.match_id AND dm1.deck_id = %s
        LEFT JOIN
            deck_match AS dm2 ON m.id = dm2.match_id AND dm2.deck_id <> %s
        INNER JOIN
            deck AS d1 ON dm1.deck_id = d1.id
        LEFT JOIN
            deck AS d2 ON dm2.deck_id = d2.id
        LEFT JOIN
            person AS p ON p.id = d2.person_id
        ORDER BY
            m.date,
            m.`round`
    """.format(person_query=query.person_query())
    matches = [Container(m) for m in db().select(sql, [d.id, d.id])]
    if should_load_decks:
        opponents = [m.opponent_deck_id for m in matches if m.opponent_deck_id is not None]
        if len(opponents) > 0:
            decks = deck.load_decks('d.id IN ({ids})'.format(ids=', '.join([sqlescape(str(deck_id)) for deck_id in opponents])))
        else:
            decks = []
        decks_by_id = {d.id: d for d in decks}
    for m in matches:
        m.date = dtutil.ts2dt(m.date)
        if should_load_decks and m.opponent_deck_id is not None and decks_by_id.get(m.opponent_deck_id):
            m.opponent_deck = decks_by_id[m.opponent_deck_id]
        elif should_load_decks:
            m.opponent_deck = None
    return matches

def stats() -> Dict[str, int]:
    sql = """
        SELECT
            SUM(CASE WHEN FROM_UNIXTIME(`date`) >= NOW() - INTERVAL 1 DAY THEN 1 ELSE 0 END) AS num_matches_today,
            SUM(CASE WHEN FROM_UNIXTIME(`date`) >= NOW() - INTERVAL 7 DAY THEN 1 ELSE 0 END) AS num_matches_this_week,
            SUM(CASE WHEN FROM_UNIXTIME(`date`) >= NOW() - INTERVAL 30 DAY THEN 1 ELSE 0 END) AS num_matches_this_month,
            SUM(CASE WHEN `date` >= %s THEN 1 ELSE 0 END) AS num_matches_this_season,
            COUNT(*) AS num_matches_all_time
        FROM
            `match`
    """
    return db().select(sql, [dtutil.dt2ts(rotation.last_rotation())])[0]

def load_matches(person_id: int, season_id: Optional[int] = None) -> List[Container]:
    person_query = query.person_query(table='o')
    competition_join = query.competition_join()
    season_join = query.season_join()
    season_query = query.season_query(season_id, 'season.id')
    sql = f"""
        SELECT
            m.`date`,
            d.id AS deck_id,
            dc.normalized_name AS deck_name,
            od.id AS opponent_deck_id,
            odc.normalized_name AS opponent_deck_name,
            dm.games AS game_wins,
            odm.games AS game_losses,
            c.id AS competition_id,
            ct.name AS competition_type_name,
            c.end_date AS competition_end_date,
            {person_query} AS opponent,
            odc.wins,
            odc.draws,
            odc.losses,
            od.retired
        FROM
            `match` AS m
        INNER JOIN
            deck_match AS dm ON m.id = dm.match_id
        INNER JOIN
            deck AS d ON dm.deck_id = d.id
        INNER JOIN
            deck_cache AS dc ON d.id = dc.deck_id
        INNER JOIN
            deck_match AS odm ON dm.match_id = odm.match_id AND odm.deck_id <> d.id
        INNER JOIN
            deck AS od ON odm.deck_id = od.id
        INNER JOIN
            deck_cache AS odc ON od.id = odc.deck_id
        INNER JOIN
            person AS o ON od.person_id = o.id
        {competition_join}
        {season_join}
        WHERE
            d.person_id = %s
        AND
            {season_query}
        ORDER BY
            m.`date` DESC
    """
    matches = [Container(r) for r in db().select(sql, [person_id])]
    for m in matches:
        m.date = dtutil.ts2dt(m.date)
        m.competition_end_date = dtutil.ts2dt(m.competition_end_date)
        m.competition_url = url_for('competition', competition_id=m.competition_id)
        if Deck(m).is_in_current_run():
            m.opponent_deck_name = '(Active League Run)'
    return matches
