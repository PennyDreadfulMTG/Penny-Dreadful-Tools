from decksite.data import person
from decksite.database import db
from shared import guarantee
from shared.database import sqlescape

# Using chess numbers here would make individual matches have too much meaning. Magic matches should move your rating less because of the inherent variance in Magic.
# Fritz with the width in order to make the numbers look like chess numbers so that similar numbers are "good" and "great" even though that means a gap of 200 now means a lot less for who is going to win than it does in chess.
# See http://www.mtgeloproject.net/faq.php for some other thoughts on this (their numbers didn't quite work applied to our data, but we went with something similar that was a better fit).

STARTING_ELO = 1500
ELO_WIDTH = 1600
K_FACTOR = 12

def adjustment(elo1: int, elo2: int) -> int:
    e = expected(elo1, elo2)
    return max(round(K_FACTOR * (1 - e)), 1)

def expected(elo1: int, elo2: int) -> float:
    return 1.0 / (1 + 10**((elo2 - elo1) / ELO_WIDTH))

def adjust_elo(winning_deck_id: int, losing_deck_id: int) -> None:
    if not losing_deck_id:
        return # Intentional draws do not affect Elo.
    winner = guarantee.exactly_one(person.load_people('p.id IN (SELECT person_id FROM deck WHERE id = {winning_deck_id})'.format(winning_deck_id=sqlescape(winning_deck_id))))
    loser = guarantee.exactly_one(person.load_people('p.id IN (SELECT person_id FROM deck WHERE id = {losing_deck_id})'.format(losing_deck_id=sqlescape(losing_deck_id))))
    adj = adjustment(winner.elo or STARTING_ELO, loser.elo or STARTING_ELO)
    sql = 'UPDATE person SET elo = IFNULL(elo, {starting_elo}) + %s WHERE id = %s'.format(starting_elo=sqlescape(STARTING_ELO))
    db().execute(sql, [adj, winner.id])
    db().execute(sql, [-adj, loser.id])
