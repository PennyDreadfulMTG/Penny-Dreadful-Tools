import sys
from typing import Dict, List, Optional

from decksite.data import deck, query
from decksite.database import db
from magic import oracle
from magic.models import Card
from shared import guarantee
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import DatabaseException


def load_cards(person_id: Optional[int] = None, season_id: Optional[int] = None, retry: bool = False) -> List[Card]:
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
            return load_cards(person_id, season_id, retry=True)
        print(f'Failed to preaggregate. Giving up.')
        raise e

def load_card(name: str, season_id: Optional[int] = None) -> Card:
    c = guarantee.exactly_one(oracle.load_cards([name]))
    c.decks = deck.load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card = {name})'.format(name=sqlescape(name)), season_id=season_id)
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

def playability(retry: bool = False) -> Dict[str, float]:
    sql = """
        SELECT
            name,
            playability
        FROM
            _playability
    """
    try:
        return {r['name']: r['playability'] for r in db().select(sql)}
    except DatabaseException as e:
        if not retry:
            print(f"Got {e} trying to get playability so trying to preaggregate. If this is happening on user time that's undesirable.")
            preaggregate_playability()
            return playability(retry=True)
        print(f'Failed to preaggregate. Giving up.')
        raise e

def preaggregate() -> None:
    preaggregate_card()
    preaggregate_card_person()
    preaggregate_playability()

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
            deck_card AS dc ON d.id = dc.deck_id
        {competition_join}
        {season_join}
        {nwdl_join}
        GROUP BY
            card,
            season.id
    """.format(competition_join=query.competition_join(),
               season_join=query.season_join(),
               nwdl_join=deck.nwdl_join()))
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
            deck_card AS dc ON d.id = dc.deck_id
        {competition_join}
        {season_join}
        {nwdl_join}
        GROUP BY
            card,
            d.person_id,
            season.id
    """.format(competition_join=query.competition_join(),
               season_join=query.season_join(),
               nwdl_join=deck.nwdl_join()))
    db().execute('DROP TABLE IF EXISTS _old_card_person_stats')
    db().execute('CREATE TABLE IF NOT EXISTS _card_person_stats (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _card_person_stats TO _old_card_person_stats, _new_card_person_stats TO _card_person_stats')
    db().execute('DROP TABLE IF EXISTS _old_card_person_stats')

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
    db().execute('DROP TABLE IF EXISTS _new_playability')
    sql = """
        CREATE TABLE IF NOT EXISTS _new_playability (
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
    """.format(high=high)
    db().execute(sql)
    db().execute('DROP TABLE IF EXISTS _old_playability')
    db().execute('CREATE TABLE IF NOT EXISTS _playability (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _playability TO _old_playability, _new_playability TO _playability')
    db().execute('DROP TABLE IF EXISTS _old_playability')

def card_exists(name: str) -> bool:
    sql = 'SELECT EXISTS(SELECT * FROM deck_card WHERE card = %s LIMIT 1)'
    return bool(db().value(sql, [name]))
