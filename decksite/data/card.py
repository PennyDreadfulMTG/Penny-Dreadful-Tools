from decksite.data import deck, guarantee
from decksite.database import db
from magic import oracle, rotation
from shared.container import Container
from shared.database import sqlescape


def played_cards(where='1 = 1'):
    sql = """
        SELECT
            card AS name,
            {all_select},
            {season_select},
            {week_select}
        FROM
            deck_card AS dc
        INNER JOIN
            deck AS d ON dc.deck_id = d.id
        {nwdl_join}
        WHERE
            {where}
        GROUP BY
            dc.card
        ORDER BY
            season_num_decks DESC,
            SUM(CASE WHEN dsum.created_date >= %s THEN dsum.wins - dsum.losses ELSE 0 END) DESC,
            name
    """.format(all_select=deck.nwdl_all_select(), season_select=deck.nwdl_season_select(), week_select=deck.nwdl_week_select(), nwdl_join=deck.nwdl_join(), where=where)
    cs = [Container(r) for r in db().execute(sql, [int(rotation.last_rotation().timestamp())])]
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
        SELECT
            card AS name
        FROM
            deck_card AS dc
        INNER JOIN
            deck AS d ON dc.deck_id = d.id
        WHERE
            deck_id
        IN (
            SELECT
                DISTINCT deck_id
            FROM
                deck_match
        ) -- Only include cards that actually got played competitively rather than just posted to Goldfish as "new cards this season" or similar.
        GROUP BY
            card
        HAVING
            COUNT(DISTINCT d.person_id) = 1
        AND
            MAX(d.person_id) = {person_id} -- In MySQL 5.7+ this could/should be ANY_VALUE not MAX but this works with any version. The COUNT(DISTINCT  p.id) ensures this only has one possible value but MySQL can't work that out.-- In MySQL 5.7+ this could/should be ANY_VALUE not MAX but this works with any version. The COUNT(DISTINCT  p.id) ensures this only has one possible value but MySQL can't work that out.
    """.format(person_id=sqlescape(person_id))
    cards = {c.name: c for c in oracle.load_cards()}
    return [cards[r['name']] for r in db().execute(sql)]

def playability():
    sql = """
        SELECT
            card AS name,
            COUNT(*) AS played
        FROM
            deck_card
        GROUP BY
            card
    """
    rs = [Container(r) for r in db().execute(sql)]
    high = max([c.played for c in rs])
    return {c.name: (c.played / high) for c in rs}
