from decksite.data import deck, elo, query
from decksite.database import db
from shared import dtutil
from shared.container import Container
from shared.database import sqlescape


# pylint: disable=too-many-arguments
def insert_match(dt, left_id, left_games, right_id, right_games, round_num=None, elimination=False, mtgo_match_id=None):
    match_id = db().insert("INSERT INTO `match` (`date`, `round`, elimination, mtgo_id) VALUES (%s, %s, %s, %s)", [dtutil.dt2ts(dt), round_num, elimination, mtgo_match_id])
    sql = 'INSERT INTO deck_match (deck_id, match_id, games) VALUES (%s, %s, %s)'
    db().execute(sql, [left_id, match_id, left_games])
    if right_id is not None: # Don't insert matches or adjust Elo for the bye.
        db().execute(sql, [right_id, match_id, right_games])
        elo.adjust_elo(left_id if left_games > right_games else right_id, left_id if left_games < right_games else right_id)
    return match_id

def get_matches(d, should_load_decks=False):
    sql = """
        SELECT
            m.`date`, m.id, m.round, m.elimination,
            dm1.games AS game_wins,
            dm2.deck_id AS opponent_deck_id, IFNULL(dm2.games, 0) AS game_losses,
            d2.name AS opponent_deck_name,
            {person_query} AS opponent
        FROM `match` AS m
        INNER JOIN deck_match AS dm1 ON m.id = dm1.match_id AND dm1.deck_id = %s
        LEFT JOIN deck_match AS dm2 ON m.id = dm2.match_id AND dm2.deck_id <> %s
        INNER JOIN deck AS d1 ON dm1.deck_id = d1.id
        LEFT JOIN deck AS d2 ON dm2.deck_id = d2.id
        LEFT JOIN person AS p ON p.id = d2.person_id
        ORDER BY m.date, round
    """.format(person_query=query.person_query())
    matches = [Container(m) for m in db().execute(sql, [d.id, d.id])]
    if should_load_decks:
        opponents = [m.opponent_deck_id for m in matches if m.opponent_deck_id is not None]
        if len(opponents) > 0:
            decks = deck.load_decks('d.id IN ({ids})'.format(ids=', '.join([sqlescape(str(deck_id)) for deck_id in opponents])))
        else:
            decks = []
        decks_by_id = {d.id: d for d in decks}
    for m in matches:
        m.date = dtutil.ts2dt(m.date)
        if should_load_decks and m.opponent_deck_id is not None:
            m.opponent_deck = decks_by_id[m.opponent_deck_id]
        elif should_load_decks:
            m.opponent_deck = None
    return matches
