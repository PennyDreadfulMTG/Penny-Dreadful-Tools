from munch import Munch

from magic import oracle
from shared.database import sqlescape

from decksite.data import deck, guarantee
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
    cs = [Munch(r) for r in db().execute(sql)]
    cards = {c.name: c for c in oracle.load_cards()}
    for c in cs:
        c.update(cards[c.name])
    return cs

def load_card(name):
    c = guarantee.exactly_one(oracle.load_cards([name]))
    c.decks = deck.load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card = {name})'.format(name=sqlescape(name)))
    c.wins = sum(filter(None, [d.wins for d in c.decks]))
    c.losses = sum(filter(None, [d.losses for d in c.decks]))
    c.draws = sum(filter(None, [d.draws for d in c.decks]))
    c.played_competitively = c.wins or c.losses or c.draws
    return c
