from magic import oracle, rotation
from shared.container import Container
from shared.database import sqlescape

from decksite.data import deck, guarantee
from decksite.database import db

def played_cards(where='1 = 1'):
    sql = """
        SELECT
            card AS name,
            COUNT(card) AS `all.n_decks`,
            SUM(CASE WHEN maindeck_n > 0 THEN 1 ELSE 0 END) AS `all.n_maindecks`,
            SUM(CASE WHEN sideboard_n > 0 THEN 1 ELSE 0 END) AS `all.n_sideboards`,
            SUM(maindeck_n + sideboard_n) AS `all.count_decks`,
            SUM(maindeck_n) AS `all.count_maindecks`,
            SUM(sideboard_n) AS `all.count_sideboards`,
            SUM(wins) AS `all.wins`,
            SUM(losses) AS `all.losses`,
            SUM(draws) AS `all.draws`,
            IFNULL(ROUND((SUM(wins) / SUM(wins + losses)) * 100, 1), '') AS `all.win_percent`,

            SUM(CASE WHEN created_date >= %s THEN 1 ELSE 0 END) AS `season.n_decks`,
            SUM(CASE WHEN created_date >= %s AND maindeck_n > 0 THEN 1 ELSE 0 END) AS `season.n_maindecks`,
            SUM(CASE WHEN created_date >= %s AND sideboard_n > 0 THEN 1 ELSE 0 END) AS `season.n_sideboards`,
            SUM(CASE WHEN created_date >= %s THEN maindeck_n + sideboard_n ELSE 0 END) AS `season.count_decks`,
            SUM(CASE WHEN created_date >= %s THEN maindeck_n ELSE 0 END) AS `season.count_maindecks`,
            SUM(CASE WHEN created_date >= %s THEN sideboard_n ELSE 0 END) AS `season.count_sideboards`,
            SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END) AS `season.wins`,
            SUM(CASE WHEN created_date >= %s THEN losses ELSE 0 END) AS `season.losses`,
            SUM(CASE WHEN created_date >= %s THEN draws ELSE 0 END) AS `season.draws`,
            ROUND((SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END + CASE WHEN created_date >= %s THEN losses ELSE 0 END)) * 100, 1) AS `season.win_percent`
        FROM (
            SELECT
                d.created_date,
                d.person_id,
                d.wins,
                d.draws,
                d.losses,
                card,
                maindeck_n,
                sideboard_n
            FROM (
                    SELECT
                        card,
                        deck_id,
                        SUM(CASE WHEN NOT sideboard THEN n ELSE 0 END) AS maindeck_n,
                        SUM(CASE WHEN sideboard THEN n ELSE 0 END) AS sideboard_n
                    FROM deck_card
                    GROUP BY deck_id, card
            ) AS dc
            LEFT JOIN deck AS d ON d.id = dc.deck_id
            WHERE {where}
        ) AS deck_card_agg
        GROUP BY card
        ORDER BY `season.n_decks` DESC, `season.count_decks` DESC, `season.n_maindecks` DESC, `season.count_maindecks` DESC, `all.n_decks` DESC, `all.count_decks` DESC, `all.n_maindecks` DESC, `all.count_maindecks` DESC
    """.format(where=where)
    cs = [Container(r) for r in db().execute(sql, [rotation.last_rotation().timestamp()] * 12)]
    cards = oracle.cards_by_name()
    for c in cs:
        c.update(cards[c.name])
    return cs

def load_card(name):
    c = guarantee.exactly_one(oracle.load_cards([name]))
    c.decks = deck.load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card = {name})'.format(name=sqlescape(name)))
    c.season = Container()
    c.all = Container()
    c.all.wins = sum(filter(None, [d.wins for d in c.decks]))
    c.all.losses = sum(filter(None, [d.losses for d in c.decks]))
    c.all.draws = sum(filter(None, [d.draws for d in c.decks]))
    if c.all.wins or c.all.losses or c.all.draws:
        c.all.win_percent = round((c.all.wins / (c.all.wins + c.all.losses)) * 100, 1)
    else:
        c.all.win_percent = ''
    c.all.num_decks = len(c.decks)
    season_decks = [d for d in c.decks if d.created_date > rotation.last_rotation()]
    c.season.wins = sum(filter(None, [d.wins for d in season_decks]))
    c.season.losses = sum(filter(None, [d.losses for d in season_decks]))
    c.season.draws = sum(filter(None, [d.draws for d in season_decks]))
    if c.season.wins or c.season.losses or c.season.draws:
        c.season.win_percent = round((c.season.wins / (c.season.wins + c.season.losses)) * 100, 1)
    else:
        c.season.win_percent = ''
    c.season.num_decks = len(season_decks)
    c.played_competitively = c.all.wins or c.all.losses or c.all.draws
    return c

def only_played_by(person_id):
    sql = """
        SELECT card AS name, p.id
        FROM deck_card AS dc
        INNER JOIN deck AS d ON d.id = dc.deck_id
        INNER JOIN person AS p ON p.id = d.person_id
        GROUP BY card
        HAVING COUNT(DISTINCT p.id) = 1 AND p.id = {person_id} AND SUM(d.wins + d.draws + d.losses) > 0
    """.format(person_id=sqlescape(person_id))
    cs = [Container(r) for r in db().execute(sql)]
    cards = {c.name: c for c in oracle.load_cards()}
    for c in cs:
        c.update(cards[c.name])
    return cs
