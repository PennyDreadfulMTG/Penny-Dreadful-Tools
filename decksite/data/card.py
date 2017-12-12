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
            SUM(wins) AS `all_wins`,
            SUM(losses) AS `all_losses`,
            SUM(draws) AS `all_draws`,
            IFNULL(ROUND((SUM(wins) / SUM(wins + losses)) * 100, 1), '') AS `all_win_percent`,

            SUM(CASE WHEN created_date >= %s THEN 1 ELSE 0 END) AS `season_num_decks`,
            SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END) AS `season_wins`,
            SUM(CASE WHEN created_date >= %s THEN losses ELSE 0 END) AS `season_losses`,
            SUM(CASE WHEN created_date >= %s THEN draws ELSE 0 END) AS `season_draws`,
            ROUND((SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN created_date >= %s THEN wins ELSE 0 END + CASE WHEN created_date >= %s THEN losses ELSE 0 END)) * 100, 1) AS `season_win_percent`,

            SUM(CASE WHEN created_date >= UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN 1 ELSE 0 END) AS `week_num_decks`,
            SUM(CASE WHEN created_date >= UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN wins ELSE 0 END) AS `week_wins`,
            SUM(CASE WHEN created_date >= UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN losses ELSE 0 END) AS `week_losses`,
            SUM(CASE WHEN created_date >= UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN draws ELSE 0 END) AS `week_draws`,
            ROUND((SUM(CASE WHEN created_date >= UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN wins ELSE 0 END) / SUM(CASE WHEN created_date >= UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN wins ELSE 0 END + CASE WHEN created_date >= UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN losses ELSE 0 END)) * 100, 1) AS `week_win_percent`
        FROM deck_card AS dc
        LEFT JOIN deck AS d ON d.id = dc.deck_id
        WHERE {where}
        GROUP BY dc.card
        ORDER BY `season_num_decks` DESC, SUM(wins) - SUM(losses), name
    """.format(where=where)
    cs = [Container(r) for r in db().execute(sql, [int(rotation.last_rotation().timestamp())] * 7)]
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
