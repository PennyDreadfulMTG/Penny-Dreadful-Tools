from typing import Dict, List, Optional

from decksite.data import deck, query
from decksite.database import db
from magic import oracle
from magic.models.card import Card
from shared import guarantee
from shared.container import Container
from shared.database import sqlescape


def played_cards(where: str = '1 = 1', season_id: Optional[int] = None) -> List[Card]:
    sql = """
        SELECT
            card AS name,
            {all_select},
            {season_select}, -- We use the season data on the homepage to calculate movement, even though we no longer use it on /cards/.
            {week_select}
        FROM
            deck_card AS dc
        INNER JOIN
            deck AS d ON dc.deck_id = d.id
        {season_join}
        {nwdl_join}
        WHERE ({where}) AND ({season_query})
        GROUP BY
            dc.card
        ORDER BY
            all_num_decks DESC,
            SUM(dsum.wins - dsum.losses) DESC,
            name
    """.format(all_select=deck.nwdl_all_select(), season_select=deck.nwdl_season_select(), week_select=deck.nwdl_week_select(), season_join=query.season_join(), nwdl_join=deck.nwdl_join(), where=where, season_query=query.season_query(season_id))
    cs = [Container(r) for r in db().execute(sql)]
    cards = oracle.cards_by_name()
    for c in cs:
        c.update(cards[c.name])
    return cs

def played_cards_by_person(person_id: int, season_id: Optional[int] = None) -> List[Card]:
    return played_cards('d.person_id = {person_id}'.format(person_id=sqlescape(person_id)), season_id=season_id)

def load_card(name: str, season_id: Optional[int] = None) -> Card:
    c = guarantee.exactly_one(oracle.load_cards([name]))
    c.decks = deck.load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card = {name})'.format(name=sqlescape(name)), season_id=season_id)
    c.all = Container()
    c.all_wins = sum(filter(None, [d.wins for d in c.decks]))
    c.all_losses = sum(filter(None, [d.losses for d in c.decks]))
    c.all_draws = sum(filter(None, [d.draws for d in c.decks]))
    if c.all_wins or c.all_losses:
        c.all_win_percent = round((c.all_wins / (c.all_wins + c.all_losses)) * 100, 1)
    else:
        c.all_win_percent = ''
    c.all_num_decks = len(c.decks)
    c.played_competitively = c.all_wins or c.all_losses or c.all_draws
    return c

def only_played_by(person_id: int, season_id: Optional[int] = None) -> List[Card]:
    sql = """
        SELECT
            card AS name
        FROM
            deck_card AS dc
        INNER JOIN
            deck AS d ON dc.deck_id = d.id
        {season_join}
        WHERE
            deck_id
        IN
            (
                SELECT
                    DISTINCT deck_id
                FROM
                    deck_match
            ) -- Only include cards that actually got played competitively rather than just posted to Goldfish as "new cards this season" or similar.
        AND
            ({season_query})
        GROUP BY
            card
        HAVING
            COUNT(DISTINCT d.person_id) = 1
        AND
            MAX(d.person_id) = {person_id} -- In MySQL 5.7+ this could/should be ANY_VALUE not MAX but this works with any version. The COUNT(DISTINCT  p.id) ensures this only has one possible value but MySQL can't work that out.-- In MySQL 5.7+ this could/should be ANY_VALUE not MAX but this works with any version. The COUNT(DISTINCT  p.id) ensures this only has one possible value but MySQL can't work that out.
    """.format(season_join=query.season_join(), season_query=query.season_query(season_id), person_id=sqlescape(person_id))
    cards = {c.name: c for c in oracle.load_cards()}
    return [cards[r['name']] for r in db().execute(sql)]

def playability() -> Dict[str, float]:
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
