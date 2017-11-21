from magic import oracle, rotation
from shared.container import Container
from shared.database import sqlescape

from decksite.data import deck, guarantee
from decksite.database import db

def played_cards(where='1 = 1'):
    sql = """
        SELECT
            card AS name,
            COUNT(card) AS `all_num_decks`,
            SUM(CASE WHEN maindeck_n > 0 THEN 1 ELSE 0 END) AS `all_n_maindecks`,
            SUM(CASE WHEN sideboard_n > 0 THEN 1 ELSE 0 END) AS `all_n_sideboards`,
            SUM(maindeck_n + sideboard_n) AS `all_count_decks`,
            SUM(maindeck_n) AS `all_count_maindecks`,
            SUM(sideboard_n) AS `all_count_sideboards`,
            SUM(wins) AS `all_wins`,
            SUM(losses) AS `all_losses`,
            SUM(draws) AS `all_draws`,
            IFNULL(ROUND((SUM(wins) / SUM(wins + losses)) * 100, 1), '') AS `all_win_percent`,

            SUM(CASE WHEN created_date >= %s THEN 1 ELSE 0 END) AS `season_num_decks`,
            SUM(CASE WHEN created_date >= %s AND maindeck_n > 0 THEN 1 ELSE 0 END) AS `season_n_maindecks`,
            SUM(CASE WHEN created_date >= %s AND sideboard_n > 0 THEN 1 ELSE 0 END) AS `season_n_sideboards`,
            SUM(CASE WHEN created_date >= %s THEN maindeck_n + sideboard_n ELSE 0 END) AS `season_count_decks`,
            SUM(CASE WHEN created_date >= %s THEN maindeck_n ELSE 0 END) AS `season_count_maindecks`,
            SUM(CASE WHEN created_date >= %s THEN sideboard_n ELSE 0 END) AS `season_count_sideboards`,
            SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END) AS `season_wins`,
            SUM(CASE WHEN created_date >= %s THEN losses ELSE 0 END) AS `season_losses`,
            SUM(CASE WHEN created_date >= %s THEN draws ELSE 0 END) AS `season_draws`,
            ROUND((SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END + CASE WHEN created_date >= %s THEN losses ELSE 0 END)) * 100, 1) AS `season_win_percent`
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
        ORDER BY `season_num_decks` DESC, `season_count_decks` DESC, `season_n_maindecks` DESC, `season_count_maindecks` DESC, `all_num_decks` DESC, `all_count_decks` DESC, `all_n_maindecks` DESC, `all_count_maindecks` DESC
    """.format(where=where)
    cs = [Container(r) for r in db().execute(sql, [int(rotation.last_rotation().timestamp())] * 12)]
    cards = oracle.cards_by_name()
    for c in cs:
        c.update(cards[c.name])
    return cs

def load_card(name):
    c = guarantee.exactly_one(oracle.load_cards([name]))
    c.decks = deck.load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card = {name})'.format(name=sqlescape(name)))
    c.season = Container()
    c.all = Container()
    c.all_wins = sum(filter(None, [d.wins for d in c.decks]))
    c.all_losses = sum(filter(None, [d.losses for d in c.decks]))
    c.all_draws = sum(filter(None, [d.draws for d in c.decks]))
    if c.all_wins or c.all_losses or c.all_draws:
        c.all_win_percent = round((c.all_wins / (c.all_wins + c.all_losses)) * 100, 1)
    else:
        c.all_win_percent = ''
    c.all_num_decks = len(c.decks)
    season_decks = [d for d in c.decks if d.created_date > rotation.last_rotation()]
    c.season_wins = sum(filter(None, [d.wins for d in season_decks]))
    c.season_losses = sum(filter(None, [d.losses for d in season_decks]))
    c.season_draws = sum(filter(None, [d.draws for d in season_decks]))
    if c.season_wins or c.season_losses or c.season_draws:
        c.season_win_percent = round((c.season_wins / (c.season_wins + c.season_losses)) * 100, 1)
    else:
        c.season_win_percent = ''
    c.season_num_decks = len(season_decks)
    c.played_competitively = c.all_wins or c.all_losses or c.all_draws
    return c

def only_played_by(person_id):
    sql = """
        SELECT card AS name, p.id
        FROM deck_card AS dc
        LEFT JOIN deck AS d ON d.id = dc.deck_id
        LEFT JOIN person AS p ON p.id = d.person_id
        GROUP BY card
        HAVING COUNT(DISTINCT p.id) = 1 AND p.id = {person_id} AND SUM(d.wins + d.draws + d.losses) > 0
    """.format(person_id=sqlescape(person_id))
    cs = [Container(r) for r in db().execute(sql)]
    cards = {c.name: c for c in oracle.load_cards()}
    for c in cs:
        c.update(cards[c.name])
    return cs
