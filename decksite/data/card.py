import sys
from typing import Dict, List, Optional

from decksite.data import deck, preaggregation, query
from decksite.database import db
from magic import oracle
from magic.models import Card
from shared import guarantee
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import retry_after_calling


def load_card(name: str, season_id: Optional[int] = None) -> Card:
    c = guarantee.exactly_one(oracle.load_cards([name]))
    c.decks = deck.load_decks(query.card_where(name), season_id=season_id)
    c.wins, c.losses, c.draws, c.tournament_wins, c.tournament_top8s, c.perfect_runs = 0, 0, 0, 0, 0, 0
    c.wins_tournament, c.losses_tournament, c.draws_tournament = 0, 0, 0
    c.decks_tournament = []
    for d in c.decks:
        c.wins += d.get('wins', 0)
        c.losses += d.get('losses', 0)
        c.draws += d.get('draws', 0)
        c.tournament_wins += 1 if d.get('finish') == 1 else 0
        c.tournament_top8s += 1 if (d.get('finish') or sys.maxsize) <= 8 else 0
        c.perfect_runs += 1 if d.get('source_name') == 'League' and d.get('wins', 0) >= 5 and d.get('losses', 0) == 0 else 0
        if d.competition_type_name == 'Gatherling':
            c.decks_tournament.append(d)
            c.wins_tournament += (d.get('wins') or 0)
            c.losses_tournament += (d.get('losses') or 0)
            c.draws_tournament += (d.get('draws') or 0)
    if c.wins or c.losses:
        c.win_percent = round((c.wins / (c.wins + c.losses)) * 100, 1)
    else:
        c.win_percent = ''
    if c.wins_tournament or c.losses_tournament:
        c.win_percent_tournament = round((c.wins_tournament / (c.wins_tournament + c.losses_tournament)) * 100, 1)
    else:
        c.win_percent_tournament = ''
    c.num_decks = len(c.decks)
    c.num_decks_tournament = len(c.decks_tournament)
    c.played_competitively = c.wins or c.losses or c.draws
    return c

def preaggregate() -> None:
    preaggregate_card()
    preaggregate_card_person()
    preaggregate_playability()
    preaggregate_unique()
    preaggregate_trailblazer()

def preaggregate_card() -> None:
    table = '_card_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            num_decks INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            wins_tournament INT NOT NULL,
            losses_tournament INT NOT NULL,
            draws_tournament INT NOT NULL,
            PRIMARY KEY (season_id, name),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            card AS name,
            season.id AS season_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(wins), 0) AS wins,
            IFNULL(SUM(losses), 0) AS losses,
            IFNULL(SUM(draws), 0) AS draws,
            SUM(CASE WHEN wins >= 5 AND losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            SUM(CASE WHEN (d.id IS NOT NULL) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS num_decks_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN wins ELSE 0 END), 0) AS wins_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN losses ELSE 0 END), 0) AS losses_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN draws ELSE 0 END), 0) AS draws_tournament
        FROM
            deck AS d
        INNER JOIN
            -- Eiliminate maindeck/sideboard double-counting with DISTINCT. See #5493.
            (SELECT DISTINCT card, deck_id FROM deck_card) AS dc ON d.id = dc.deck_id
        {competition_join}
        {season_join}
        {nwdl_join}
        GROUP BY
            card,
            season.id
    """.format(table=table,
               competition_join=query.competition_join(),
               season_join=query.season_join(),
               nwdl_join=deck.nwdl_join())
    preaggregation.preaggregate(table, sql)

def preaggregate_card_person() -> None:
    table = '_card_person_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            person_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            wins_tournament INT NOT NULL,
            losses_tournament INT NOT NULL,
            draws_tournament INT NOT NULL,
            PRIMARY KEY (season_id, person_id, name),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id)  ON UPDATE CASCADE ON DELETE CASCADE,
            INDEX idx_person_id_name (person_id, name)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            card AS name,
            season.id AS season_id,
            d.person_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(wins), 0) AS wins,
            IFNULL(SUM(losses), 0) AS losses,
            IFNULL(SUM(draws), 0) AS draws,
            SUM(CASE WHEN wins >= 5 AND losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            SUM(CASE WHEN (d.id IS NOT NULL) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS num_decks_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN wins ELSE 0 END), 0) AS wins_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN losses ELSE 0 END), 0) AS losses_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN draws ELSE 0 END), 0) AS draws_tournament
        FROM
            deck AS d
        INNER JOIN
            -- Eiliminate maindeck/sideboard double-counting with DISTINCT. See #5493.
            (SELECT DISTINCT card, deck_id FROM deck_card) AS dc ON d.id = dc.deck_id
        {competition_join}
        {season_join}
        {nwdl_join}
        GROUP BY
            card,
            d.person_id,
            season.id
    """.format(table=table,
               competition_join=query.competition_join(),
               season_join=query.season_join(),
               nwdl_join=deck.nwdl_join())
    preaggregation.preaggregate(table, sql)

def preaggregate_playability() -> None:
    sql = """
        SELECT
            card AS name,
            COUNT(*) AS played
        FROM
            deck_card
        GROUP BY
            card
    """
    rs = db().select(sql)
    high = max([r['played'] for r in rs] + [0])
    table = '_playability'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,\
            playability DECIMAL(3,2),
            PRIMARY KEY (name)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            card AS name,
            ROUND(COUNT(*) / {high}, 2) AS playability
        FROM
            deck_card
        GROUP BY
            card
    """.format(table=table, high=high)
    preaggregation.preaggregate(table, sql)

def preaggregate_unique() -> None:
    table = '_unique_cards'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            card VARCHAR(100) NOT NULL,
            person_id INT NOT NULL,
            PRIMARY KEY (card, person_id),
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        )
        SELECT
            card, person_id
        FROM
            deck_card AS dc
        INNER JOIN
            deck AS d ON dc.deck_id = d.id
        WHERE
            d.id IN (SELECT deck_id FROM deck_match GROUP BY deck_id HAVING COUNT(*) >= 3)
        GROUP BY
            card
        HAVING
            COUNT(DISTINCT person_id) = 1
    """.format(table=table)
    preaggregation.preaggregate(table, sql)

def preaggregate_trailblazer() -> None:
    table = '_trailblazer_cards'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            card VARCHAR(100) NOT NULL,
            deck_id INT NOT NULL,
            PRIMARY KEY (card, deck_id),
            FOREIGN KEY (deck_id) REFERENCES deck (id) ON UPDATE CASCADE ON DELETE CASCADE
        )
        SELECT
            d.id AS deck_id,
            card,
            MIN(d.created_date) AS `date`
        FROM
            deck_card AS dc
        INNER JOIN
            deck AS d ON dc.deck_id = d.id
        INNER JOIN
            deck_match AS dm ON dm.deck_id = d.id
        {competition_join}
        WHERE
            d.id IN (SELECT deck_id FROM deck_match GROUP BY deck_id HAVING COUNT(*) >= 3)
        GROUP BY
            card
    """.format(table=table, competition_join=query.competition_join())
    preaggregation.preaggregate(table, sql)

@retry_after_calling(preaggregate)
def load_cards(person_id: Optional[int] = None, season_id: Optional[int] = None) -> List[Card]:
    if person_id:
        table = '_card_person_stats'
        where = 'person_id = {person_id}'.format(person_id=sqlescape(person_id))
        group_by = 'person_id, name'
    else:
        table = '_card_stats'
        where = 'TRUE'
        group_by = 'name'
    sql = """
        SELECT
            name,
            SUM(num_decks) AS num_decks,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            SUM(wins - losses) AS record,
            SUM(num_decks_tournament) AS num_decks_tournament,
            SUM(wins_tournament) AS wins_tournament,
            SUM(losses_tournament) AS losses_tournament,
            SUM(draws_tournament) AS draws_tournament,
            SUM(wins_tournament - losses_tournament) AS record_tournament,
            SUM(perfect_runs) AS perfect_runs,
            SUM(tournament_wins) AS tournament_wins,
            SUM(tournament_top8s) AS tournament_top8s,
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS win_percent,
            IFNULL(ROUND((SUM(wins_tournament) / NULLIF(SUM(wins_tournament + losses_tournament), 0)) * 100, 1), '') AS win_percent_tournament
        FROM
            {table} AS cs
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            {group_by}
        ORDER BY
            num_decks DESC,
            record,
            name
    """.format(table=table, season_query=query.season_query(season_id), where=where, group_by=group_by)
    cs = [Container(r) for r in db().select(sql)]
    cards = oracle.cards_by_name()
    for c in cs:
        c.update(cards[c.name])
    return cs

@retry_after_calling(preaggregate_playability)
def playability() -> Dict[str, float]:
    sql = """
        SELECT
            name,
            playability
        FROM
            _playability
    """
    return {r['name']: r['playability'] for r in db().select(sql)}

@retry_after_calling(preaggregate_unique)
def unique_cards_played(person_id: int) -> List[str]:
    sql = """
        SELECT
            card
        FROM
            _unique_cards
        WHERE
            person_id = %s
    """
    return db().values(sql, [person_id])

@retry_after_calling(preaggregate_trailblazer)
def trailblazer_cards(person_id: int) -> List[str]:
    sql = """
        SELECT
            card
        FROM
            _trailblazer_cards AS tc
        INNER JOIN
            deck AS d ON tc.deck_id = d.id
        WHERE
            d.person_id = %s
    """
    return db().values(sql, [person_id])

def card_exists(name: str) -> bool:
    sql = 'SELECT EXISTS(SELECT * FROM deck_card WHERE card = %s LIMIT 1)'
    return bool(db().value(sql, [name]))
