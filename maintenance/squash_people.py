from decksite.data import person
from decksite.database import db
from shared import logger
from shared.container import Container

from . import elo

DAILY = True

USERNAME_COLUMNS = ['mtgo_username', 'tappedout_username', 'mtggoldfish_username']

# Find people with identical usernames across systems and squash them together.
def run() -> None:
    run_elo = False
    for i in range(0, len(USERNAME_COLUMNS)):
        for j in range(i + 1, len(USERNAME_COLUMNS)):
            sql = f"""
                SELECT p1.id AS p1_id, p2.id AS p2_id, '{USERNAME_COLUMNS[i]}' AS col1, '{USERNAME_COLUMNS[j]}' AS col2
                FROM person AS p1
                LEFT JOIN person AS p2
                ON p1.{USERNAME_COLUMNS[i]} = p2.{USERNAME_COLUMNS[j]} AND p1.id <> p2.id
                WHERE p1.id IS NOT NULL AND p2.id IS NOT NULL
            """
            pairs = [Container(row) for row in db().select(sql)]
            if len(pairs) > 0:
                run_elo = True
            for pair in pairs:
                person.squash(pair.p1_id, pair.p2_id, pair.col1, pair.col2)
    if run_elo:
        logger.warning('Running maintenance task to correct all Elo ratings.')
        elo.run()
