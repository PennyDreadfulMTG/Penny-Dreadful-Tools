from munch import Munch

from magic import oracle
from shared.database import sqlescape

from decksite.data import deck
from decksite.database import db

def played_cards():
    sql = """
        SELECT
            card AS name,
            COUNT(card) AS n_decks,
            SUM(CASE WHEN sideboard THEN 0 ELSE 1 END) AS n_maindecks,
            SUM(CASE WHEN sideboard THEN 1 ELSE 0 END) AS n_sideboards,
            SUM(n) AS count_decks,
            SUM(CASE WHEN sideboard THEN 0 ELSE n END) AS count_maindecks,
            SUM(CASE WHEN sideboard THEN n ELSE 0 END) AS count_sideboards
        FROM deck_card
        GROUP BY card
        ORDER BY n_decks DESC, count_decks DESC, n_maindecks DESC, count_maindecks DESC
    """
    return [Munch(r) for r in db().execute(sql)]

def load_card(name):
    c = oracle.load_cards([name])[0]
    c.decks = deck.load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card = {name})'.format(name=sqlescape(name)))
    return c
