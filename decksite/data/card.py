from munch import Munch

from magic import oracle, rotation
from shared.database import sqlescape

from decksite.data import deck, guarantee
from decksite.database import db

def played_cards(where_clause='1 = 1'):
    sql = """
        SELECT
            card AS name,
            COUNT(card) AS n_decks_all,
            SUM(CASE WHEN maindeck_n > 0 THEN 1 ELSE 0 END) AS n_maindecks_all,
            SUM(CASE WHEN sideboard_n > 0 THEN 1 ELSE 0 END) AS n_sideboards_all,
            SUM(maindeck_n + sideboard_n) AS count_decks_all,
            SUM(maindeck_n) AS count_maindecks_all,
            SUM(sideboard_n) AS count_sideboards_all,
            SUM(wins) AS wins_all,
            SUM(losses) AS losses_all,
            SUM(draws) AS draws_all,
            ROUND((SUM(wins) / SUM(wins + losses)) * 100, 1) AS win_percent_all,

            SUM(CASE WHEN created_date >= %s THEN 1 ELSE 0 END) AS n_decks_season,
            SUM(CASE WHEN created_date >= %s AND maindeck_n > 0 THEN 1 ELSE 0 END) AS n_maindecks_season,
            SUM(CASE WHEN created_date >= %s AND sideboard_n > 0 THEN 1 ELSE 0 END) AS n_sideboards_season,
            SUM(CASE WHEN created_date >= %s THEN maindeck_n + sideboard_n ELSE 0 END) AS count_decks_season,
            SUM(CASE WHEN created_date >= %s THEN maindeck_n ELSE 0 END) AS count_maindecks_season,
            SUM(CASE WHEN created_date >= %s THEN sideboard_n ELSE 0 END) AS count_sideboards_season,
            SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END) AS wins_season,
            SUM(CASE WHEN created_date >= %s THEN losses ELSE 0 END) AS losses_season,
            SUM(CASE WHEN created_date >= %s THEN draws ELSE 0 END) AS draws_season,
            ROUND((SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END + CASE WHEN created_date >= %s THEN losses ELSE 0 END)) * 100, 1) AS win_percent_season
        FROM
            (SELECT
                d.created_date,
                d.person_id,
                dc.card,
                SUM(CASE WHEN NOT dc.sideboard THEN n ELSE 0 END) AS maindeck_n,
                SUM(CASE WHEN dc.sideboard THEN n ELSE 0 END) AS sideboard_n,
                d.wins,
                d.draws,
                d.losses
            FROM
                deck_card AS dc
            INNER JOIN
                deck AS d ON d.id = dc.deck_id
            GROUP BY
                deck_id, card) AS deck_card_agg
        WHERE {where_clause}
        GROUP BY card
        ORDER BY n_decks_season DESC, count_decks_season DESC, n_maindecks_season DESC, count_maindecks_season DESC
    """.format(where_clause=where_clause)
    cs = [Munch(r) for r in db().execute(sql, [rotation.last_rotation().timestamp()] * 12)]
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

def only_played_by(person_id):
    sql = """
        SELECT card AS name, p.id
        FROM deck_card AS dc
        INNER JOIN deck AS d ON d.id = dc.deck_id
        INNER JOIN person AS p ON p.id = d.person_id
        GROUP BY card
        HAVING COUNT(DISTINCT p.id) = 1 AND p.id = {person_id}
    """.format(person_id=sqlescape(person_id))
    cs = [Munch(r) for r in db().execute(sql)]
    cards = {c.name: c for c in oracle.load_cards()}
    for c in cs:
        c.update(cards[c.name])
    return cs
