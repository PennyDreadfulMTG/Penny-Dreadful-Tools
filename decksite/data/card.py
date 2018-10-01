import sys
from typing import Dict, List, Optional

from decksite.data import deck, query
from decksite.database import db
from magic import oracle
from magic.models.card import Card
from shared import guarantee
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import DatabaseException


def load_cards(season_id: Optional[int] = None, person_id: Optional[int] = None, retry: bool = False) -> List[Card]:
    table = '_card_person_stats' if person_id else '_card_stats'
    where = 'TRUE'
    group_by = 'name'
    if person_id:
        group_by += ', person_id'
        where = 'person_id = {person_id}'.format(person_id=sqlescape(person_id))
    sql = """
        SELECT
            name,
            SUM(num_decks) AS all_num_decks,
            SUM(wins) AS all_wins,
            SUM(losses) AS all_losses,
            SUM(draws) AS all_draws,
            SUM(wins - losses) AS record,
            SUM(perfect_runs) AS all_perfect_runs,
            SUM(tournament_wins) AS all_tournament_wins,
            SUM(tournament_top8s) AS all_tournament_top8s,
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS all_win_percent
        FROM
            {table} AS cs
        LEFT JOIN
            ({season_table}) AS season ON season.id = cs.season_id
        WHERE
            {season_query} AND {where}
        GROUP BY
            {group_by}
        ORDER BY
            all_num_decks DESC,
            record,
            name
    """.format(table=table, season_table=query.season_table(), season_query=query.season_query(season_id), where=where, group_by=group_by)
    try:
        cs = [Container(r) for r in db().select(sql)]
        cards = oracle.cards_by_name()
        for c in cs:
            c.update(cards[c.name])
        return cs
    except DatabaseException as e:
        if not retry:
            print(f"Got {e} trying to load_cards so trying to preaggregate. If this is happening on user time that's undesirable.")
            preaggregate()
            return load_cards(season_id, person_id, retry=True)
        print(f'Failed to preaggregate. Giving up.')
        raise e

def load_card(name: str, season_id: Optional[int] = None) -> Card:
    c = guarantee.exactly_one(oracle.load_cards([name]))
    c.decks = deck.load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card = {name})'.format(name=sqlescape(name)), season_id=season_id)
    c.all_wins, c.all_losses, c.all_draws, c.all_tournament_wins, c.all_tournament_top8s, c.all_perfect_runs = 0, 0, 0, 0, 0, 0
    for d in c.decks:
        c.all_wins += d.get('wins', 0)
        c.all_losses += d.get('losses', 0)
        c.all_draws += d.get('draws', 0)
        c.all_tournament_wins += 1 if d.get('finish') == 1 else 0
        c.all_tournament_top8s += 1 if (d.get('finish') or sys.maxsize) <= 8 else 0
        c.all_perfect_runs += 1 if d.get('source_name') == 'League' and d.get('wins', 0) >= 5 and d.get('losses', 0) == 0 else 0
    if c.all_wins or c.all_losses:
        c.all_win_percent = round((c.all_wins / (c.all_wins + c.all_losses)) * 100, 1)
    else:
        c.all_win_percent = ''
    c.all_num_decks = len(c.decks)
    c.played_competitively = c.all_wins or c.all_losses or c.all_draws
    return c

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
    rs = [Container(r) for r in db().select(sql)]
    high = max([c.played for c in rs] + [0])
    return {c.name: (c.played / high) for c in rs}

def preaggregate() -> None:
    preaggregate_card()
    preaggregate_card_person()

def preaggregate_card() -> None:
    db().execute('DROP TABLE IF EXISTS _new_card_stats')
    db().execute("""
        CREATE TABLE IF NOT EXISTS _new_card_stats (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            num_decks INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
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
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s
        FROM
            deck AS d
        INNER JOIN
            deck_card AS dc ON d.id = dc.deck_id
        {season_join}
        {nwdl_join}
        GROUP BY
            card,
            season.id
    """.format(season_join=query.season_join(), nwdl_join=deck.nwdl_join()))
    db().execute('DROP TABLE IF EXISTS _old_card_stats')
    db().execute('CREATE TABLE IF NOT EXISTS _card_stats (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _card_stats TO _old_card_stats, _new_card_stats TO _card_stats')
    db().execute('DROP TABLE IF EXISTS _old_card_stats')

def preaggregate_card_person() -> None:
    db().execute('DROP TABLE IF EXISTS _new_card_person_stats')
    db().execute("""
        CREATE TABLE IF NOT EXISTS _new_card_person_stats (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            person_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            PRIMARY KEY (season_id, person_id, name),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE
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
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s
        FROM
            deck AS d
        INNER JOIN
            deck_card AS dc ON d.id = dc.deck_id
        {season_join}
        {nwdl_join}
        GROUP BY
            card,
            d.person_id,
            season.id
    """.format(season_join=query.season_join(), nwdl_join=deck.nwdl_join()))
    db().execute('DROP TABLE IF EXISTS _old_card_person_stats')
    db().execute('CREATE TABLE IF NOT EXISTS _card_person_stats (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _card_person_stats TO _old_card_person_stats, _new_card_person_stats TO _card_person_stats')
    db().execute('DROP TABLE IF EXISTS _old_card_person_stats')
