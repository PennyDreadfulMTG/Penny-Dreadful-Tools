from decksite.database import db
from shared.container import Container

from . import elo

USERNAME_COLUMNS = ['mtgo_username', 'tappedout_username', 'mtggoldfish_username']

# Find people with identical usernames across systems and squash them together.
def run():
    run_elo = False
    # pylint: disable=consider-using-enumerate
    for i in range(0, len(USERNAME_COLUMNS)):
        # pylint: disable=consider-using-enumerate
        for j in range(i + 1, len(USERNAME_COLUMNS)):
            sql = """
                SELECT p1.id AS p1_id, p2.id AS p2_id, '{col1}' AS col1, '{col2}' AS col2
                FROM person AS p1
                LEFT JOIN person AS p2
                ON p1.{col1} = p2.{col2} AND p1.id <> p2.id
                WHERE p1.id IS NOT NULL AND p2.id IS NOT NULL
            """.format(col1=USERNAME_COLUMNS[i], col2=USERNAME_COLUMNS[j])
            pairs = [Container(row) for row in db().execute(sql)]
            if len(pairs) > 0:
                run_elo = True
            for pair in pairs:
                squash(pair.p1_id, pair.p2_id, pair.col1, pair.col2)
    if run_elo:
        print('Running maintenance task to correct all Elo ratings.')
        elo.run()


def squash(p1id, p2id, col1, col2):
    print('Squashing {p1id} and {p2id} on {col1} and {col2}'.format(p1id=p1id, p2id=p2id, col1=col1, col2=col2))
    db().begin()
    new_value = db().value('SELECT {col2} FROM person WHERE id = ?'.format(col2=col2), [p2id])
    db().execute('UPDATE deck SET person_id = ? WHERE person_id = ?', [p1id, p2id])
    db().execute('DELETE FROM person WHERE id = ?', [p2id])
    db().execute('UPDATE person SET {col2} = ? WHERE id = ?'.format(col2=col2), [new_value, p1id])
    db().commit()
