import sys
from typing import Dict, List, Optional

from decksite.data import deck, query
from decksite.database import db
from magic import oracle, rotation
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
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS all_win_percent,
            SUM(CASE WHEN `day` > {season_start} THEN num_decks ELSE 0 END) AS season_num_decks,
            SUM(CASE WHEN `day` > {season_start} THEN wins ELSE 0 END) AS season_wins,
            SUM(CASE WHEN `day` > {season_start} THEN losses ELSE 0 END) AS season_losses,
            SUM(CASE WHEN `day` > {season_start} THEN draws ELSE 0 END) AS season_draws,
            SUM(CASE WHEN `day` > {season_start} THEN perfect_runs ELSE 0 END) AS season_perfect_runs,
            SUM(CASE WHEN `day` > {season_start} THEN tournament_wins ELSE 0 END) AS season_tournament_wins,
            SUM(CASE WHEN `day` > {season_start} THEN tournament_top8s ELSE 0 END) AS season_tournament_top8s,
            IFNULL(ROUND((SUM(CASE WHEN `day` > {season_start} THEN wins ELSE 0 END) / NULLIF(SUM(CASE WHEN `day` > {season_start} THEN wins + losses ELSE 0 END), 0)) * 100, 1), '') AS `season_win_percent`,
            SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN num_decks ELSE 0 END) AS week_num_decks,
            SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN wins ELSE 0 END) AS week_wins,
            SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN losses ELSE 0 END) AS week_losses,
            SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN draws ELSE 0 END) AS week_draws,
            SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN perfect_runs ELSE 0 END) AS week_perfect_runs,
            SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN tournament_wins ELSE 0 END) AS week_tournament_wins,
            SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN tournament_top8s ELSE 0 END) AS week_tournament_top8s,
            IFNULL(ROUND((SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN wins ELSE 0 END) / NULLIF(SUM(CASE WHEN `day` > UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK) THEN wins + losses ELSE 0 END), 0)) * 100, 1), '') AS `week_win_percent`
        FROM
            {table} AS cs
        LEFT JOIN
            ({season_table}) AS season ON season.start_date <= cs.day AND (season.end_date IS NULL OR season.end_date > cs.day)
        WHERE
            {season_query} AND {where}
        GROUP BY
            {group_by}
        ORDER BY
            all_num_decks DESC,
            record,
            name
    """.format(table=table, season_table=query.season_table(), season_start=int(rotation.last_rotation().timestamp()), season_query=query.season_query(season_id), where=where, group_by=group_by)
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
    high = max([c.played for c in rs])
    return {c.name: (c.played / high) for c in rs}

def preaggregate() -> None:
    preaggregate_card()
    preaggregate_card_person()

def preaggregate_card() -> None:
    db().execute('DROP TABLE IF EXISTS _new_card_stats')
    db().execute("""
        CREATE TABLE IF NOT EXISTS _new_card_stats (
            name VARCHAR(190) NOT NULL,
            `day` INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            PRIMARY KEY (`day`, name)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            card AS name,
            UNIX_TIMESTAMP(DATE(FROM_UNIXTIME(d.created_date))) AS `day`,
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
        {nwdl_join}
        GROUP BY
            card,
            `day`
    """.format(nwdl_join=deck.nwdl_join()))
    db().execute('DROP TABLE IF EXISTS _card_stats')
    db().execute('RENAME TABLE _new_card_stats TO _card_stats')

def preaggregate_card_person() -> None:
    db().execute('DROP TABLE IF EXISTS _new_card_person_stats')
    db().execute("""
        CREATE TABLE IF NOT EXISTS _new_card_person_stats (
            name VARCHAR(190) NOT NULL,
            `day` INT NOT NULL,
            person_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            PRIMARY KEY (`day`, person_id, name)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            card AS name,
            UNIX_TIMESTAMP(DATE(FROM_UNIXTIME(d.created_date))) AS `day`,
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
        {nwdl_join}
        GROUP BY
            card,
            d.person_id,
            `day`
    """.format(nwdl_join=deck.nwdl_join()))
    db().execute('DROP TABLE IF EXISTS _card_person_stats')
    db().execute('RENAME TABLE _new_card_person_stats TO _card_person_stats')
