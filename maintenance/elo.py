from typing import Dict

from decksite.data import elo, person
from decksite.database import db
from shared_web import logger

PEOPLE: Dict[str, int] = {}

def run() -> None:
    sql = """
        SELECT
            GROUP_CONCAT(d.person_id) AS people,
            GROUP_CONCAT(dm.games) AS games
        FROM
            `match` AS m
        INNER JOIN
            deck_match AS dm ON dm.match_id = m.id
        INNER JOIN
            deck AS d ON dm.deck_id = d.id
        GROUP BY
            m.id
        ORDER BY
            m.date,
            `round`
    """
    matches = db().select(sql)
    for m in matches:
        match(m)
    current = person.load_people()
    people_by_id = {p.id: p for p in current}
    sql = 'UPDATE person SET elo = %s WHERE id = %s'
    for person_id, new_elo in sorted(PEOPLE.items(), key=lambda x: -x[1]):
        p = people_by_id[int(person_id)]
        if p.elo != new_elo:
            logger.warning('{id} currently has Elo of {current_elo} and we are setting it to {new_elo}'.format(id=p.id, current_elo=p.elo, new_elo=new_elo))
            db().execute(sql, [new_elo, p.id])

def match(m: Dict[str, str]) -> None:
    if ',' not in m['games']:
        return # Ignore byes they don't affect Elo.
    if int(m['games'].split(',')[0]) == 2:
        winner = m['people'].split(',')[0]
        loser = m['people'].split(',')[1]
    elif int(m['games'].split(',')[1]) == 2:
        winner = m['people'].split(',')[1]
        loser = m['people'].split(',')[0]
    else:
        return # Ignore IDs they don't affect Elo.
    adjust(winner, loser)

def adjust(winner: str, loser: str) -> None:
    winner_elo = get_elo(winner)
    loser_elo = get_elo(loser)
    change = elo.adjustment(winner_elo, loser_elo)
    PEOPLE[winner] = winner_elo + change
    PEOPLE[loser] = loser_elo - change

def get_elo(person_id: str) -> int:
    return PEOPLE.get(person_id, elo.STARTING_ELO)
