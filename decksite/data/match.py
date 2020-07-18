import datetime
from typing import Dict, List, Optional

from flask import url_for

from decksite.data import deck, elo, query
from decksite.database import db
from magic import rotation
from magic.models import Deck
from shared import dtutil, guarantee, redis_wrapper as redis
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import TooFewItemsException


# pylint: disable=too-many-arguments
def insert_match(dt: datetime.datetime,
                 left_id: int,
                 left_games: int,
                 right_id: int,
                 right_games: int,
                 round_num: Optional[int] = None,
                 elimination: Optional[int] = None,
                 mtgo_match_id: Optional[int] = None) -> int:
    db().begin('insert_match')
    match_id = db().insert('INSERT INTO `match` (`date`, `round`, elimination, mtgo_id) VALUES (%s, %s, %s, %s)', [dtutil.dt2ts(dt), round_num, elimination, mtgo_match_id])
    update_cache(left_id, left_games, right_games, dt=dt)
    update_cache(right_id, right_games, left_games, dt=dt)
    sql = 'INSERT INTO deck_match (deck_id, match_id, games) VALUES (%s, %s, %s)'
    db().execute(sql, [left_id, match_id, left_games])
    if right_id is not None: # Don't insert matches or adjust Elo for the bye.
        db().execute(sql, [right_id, match_id, right_games])
        if left_games == right_games: # Don't adjust Elo for a draw. This is not quite right but we have so few it's not important.
            winner_id = left_id if left_games > right_games else right_id
            loser_id = left_id if left_games < right_games else right_id
            elo.adjust_elo(winner_id, loser_id)
    db().commit('insert_match')
    redis.clear(f'decksite:deck:{left_id}')
    if right_id is not None:
        redis.clear(f'decksite:deck:{right_id}')
    return match_id

def load_match(match_id: int, deck_id: int) -> Container:
    return guarantee.exactly_one(load_matches(f'm.id = {match_id} AND d.id = {deck_id}'))

def load_matches_by_deck(d: deck.Deck, should_load_decks: bool = False) -> List[Container]:
    where = f'd.id = {d.id}'
    return load_matches(where, season_id=None, should_load_decks=should_load_decks)

def load_matches_by_person(person_id: int, season_id: Optional[int] = None) -> List[Container]:
    where = f'd.person_id = {person_id}'
    return load_matches(where, season_id)

def load_matches(where: str = 'TRUE', season_id: Optional[int] = None, should_load_decks: bool = False) -> List[Container]:
    person_query = query.person_query(table='o')
    competition_join = query.competition_join()
    season_join = query.season_join()
    season_query = query.season_query(season_id, 'season.id')
    sql = f"""
        SELECT
            m.`date`,
            m.id,
            m.`round`,
            m.elimination,
            m.mtgo_id,
            d.id AS deck_id,
            dc.normalized_name AS deck_name,
            od.id AS opponent_deck_id,
            odc.normalized_name AS opponent_deck_name,
            dm.games AS game_wins,
            IFNULL(odm.games, 0) AS game_losses,
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
        LEFT JOIN
            deck_match AS odm ON dm.match_id = odm.match_id AND odm.deck_id <> d.id
        LEFT JOIN
            deck AS od ON odm.deck_id = od.id
        LEFT JOIN
            deck_cache AS odc ON od.id = odc.deck_id
        LEFT JOIN
            person AS o ON od.person_id = o.id
        {competition_join}
        {season_join}
        WHERE
            {where}
        AND
            {season_query}
        ORDER BY
            m.`date`,
            m.`round`
    """
    matches = [Container(r) for r in db().select(sql)]
    if should_load_decks:
        opponents = [m.opponent_deck_id for m in matches if m.opponent_deck_id is not None]
        if len(opponents) > 0:
            decks = deck.load_decks('d.id IN ({ids})'.format(ids=', '.join([sqlescape(str(deck_id)) for deck_id in opponents])))
        else:
            decks = []
        decks_by_id = {d.id: d for d in decks}
    for m in matches:
        m.date = dtutil.ts2dt(m.date)
        m.competition_end_date = dtutil.ts2dt(m.competition_end_date)
        m.competition_url = url_for('competition', competition_id=m.competition_id)
        if Deck(m).is_in_current_run():
            m.opponent_deck_name = '(Active League Run)'
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


def update_match(match_id: int, left_id: int, left_games: int, right_id: int, right_games: int) -> None:
    db().begin('update_match')
    m = load_match(match_id, left_id)
    prev_winner = winner(m.deck_id, m.game_wins, m.opponent_deck_id, m.game_losses)
    new_winner = winner(left_id, left_games, right_id, right_games)
    update_games(match_id, left_id, left_games)
    update_games(match_id, right_id, right_games)
    if new_winner != prev_winner:
        update_cache(m.deck_id, m.game_wins, m.game_losses, delete=True)
        update_cache(m.opponent_deck_id, m.game_losses, m.game_wins, delete=True)
        update_cache(left_id, left_games, right_games)
        update_cache(right_id, right_games, left_games)
    db().commit('update_match')
    redis.clear(f'decksite:deck:{left_id}', f'decksite:deck:{right_id}')

def update_games(match_id: int, deck_id: int, games: int) -> int:
    sql = 'UPDATE deck_match SET games = %s WHERE match_id = %s AND deck_id = %s'
    args = [games, match_id, deck_id]
    return db().execute(sql, args)

def update_cache(deck_id: int, games: int, opponent_games: int, delete: Optional[bool] = False, dt: Optional[datetime.datetime] = None) -> None:
    if games > opponent_games:
        args = [1, 0, 0]
    elif opponent_games > games:
        args = [0, 1, 0]
    else:
        args = [0, 0, 1]
    args.append(deck_id)
    symbol = '-' if delete else '+'
    active_date = dtutil.dt2ts(dt) if dt else 'active_date'
    sql = f"""
        UPDATE
            deck_cache
        SET
            wins = wins {symbol} %s, losses = losses {symbol} %s, draws = draws {symbol} %s, active_date = {active_date}
        WHERE
            deck_id = %s
    """
    db().execute(sql, args)

def delete_match(match_id: int) -> None:
    db().begin('delete_match')
    rs = db().select('SELECT deck_id, games FROM deck_match WHERE match_id = %s', [match_id])
    if not rs:
        raise TooFewItemsException('No deck_match entries found for match_id `{match_id}`')
    left_id = rs[0]['deck_id']
    left_games = rs[0]['games']
    if len(rs) > 1:
        right_id = rs[1]['deck_id']
        right_games = rs[1]['games']
    else:
        right_id, right_games = 0, 0
    update_cache(left_id, left_games, right_games, delete=True)
    update_cache(right_id, right_games, left_games, delete=True)
    sql = 'DELETE FROM `match` WHERE id = %s'
    db().execute(sql, [match_id])
    db().commit('delete_match')
    if rs:
        redis.clear(f'decksite:deck:{left_id}', f'decksite:deck:{right_id}')

def winner(left_id: int, left_games: int, right_id: int, right_games: int) -> Optional[int]:
    if left_games > right_games:
        return left_id
    if right_games > left_id:
        return right_id
    return None
