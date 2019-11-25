import re
from typing import List, Tuple

from decksite.data import preaggregation, query
from decksite.database import db as decksite_db
from logsite.database import db as logsite_db
from magic import oracle
from magic.models.card import Card
from shared import configuration
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import retry_after_calling


def preaggregate():
    preaggregate_played_person()

def preaggregate_played_person():
    table = '_played_card_person_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            person_id INT NOT NULL,
            num_decks INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            PRIMARY KEY (season_id, person_id, name),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id)  ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            name,
            season_id AS season_id,
            person_id,
            COUNT(*) AS num_decks,
            SUM(CASE WHEN my_games > your_games THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN my_games < your_games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN my_games = your_games THEN 1 ELSE 0 END) AS draws
        FROM
            (
                SELECT
                    gcp.name,
                    season.id AS season_id,
                    p.id AS person_id,
                    MAX(CASE WHEN p.id = d.person_id THEN dm.games ELSE 0 END) AS my_games,
                    MAX(CASE WHEN p.id <> d.person_id THEN dm.games ELSE 0 END) AS your_games
                FROM
                    {logsite_database}._game_card_person AS gcp
                INNER JOIN
                    person AS p ON gcp.mtgo_username = p.mtgo_username
                INNER JOIN
                    {logsite_database}.game AS g ON g.id = gcp.game_id
                INNER JOIN
                    `match` AS m ON m.mtgo_id = g.match_id
                INNER JOIN
                    deck_match AS dm ON dm.match_id = m.id
                INNER JOIN
                    deck AS d ON dm.deck_id = d.id
                {season_join}
                GROUP BY
                    name, p.id, m.id
            ) AS base
        GROUP BY
            name, person_id, season_id
    """.format(table=table, logsite_database=configuration.get('logsite_database'), season_join=query.season_join())
    print(sql)
    preaggregation.preaggregate(table, sql)

@retry_after_calling(preaggregate_played_person)
def played_cards_by_person(person_id: int, season_id: int) -> List[Card]:
    sql = """
        SELECT
            name,
            SUM(num_decks) AS num_decks,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            SUM(wins - losses) AS record,
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS win_percent
        FROM
            _played_card_person_stats
        WHERE
            person_id = %s
        AND
            {season_query}
        GROUP BY
            name
        HAVING
            name IS NOT NULL
    """.format(season_query=query.season_query(season_id))
    print(sql)
    cs = [Container(r) for r in decksite_db().select(sql, [person_id])]
    print(len(cs))
    cards = oracle.cards_by_name()
    for c in cs:
        c.update(cards[c.name])
    return cs

def process_logs() -> None:
    init()
    ids_to_process = next_ids()
    placeholders = ', '.join('%s' for v in ids_to_process)
    sql = f"""
        SELECT
            id AS game_id,
            log
        FROM
            game
        WHERE
            id IN ({placeholders})
    """
    rs = logsite_db().select(sql, ids_to_process)
    values = []
    for r in rs:
        entries = process_log(r['log'])
        for entry in entries:
            values.append([r['game_id']] + list(entry))
    sql = 'INSERT INTO _game_card_person (game_id, mtgo_username, name) VALUES '
    sql += ', '.join('(' + ', '.join(str(sqlescape(v)) for v in vs) + ')' for vs in values)
    logsite_db().execute(sql)

def next_ids():
    sql = """
        SELECT
            id AS game_id
        FROM
            game
        WHERE
            id NOT IN (
                SELECT
                    game_id
                FROM
                    _game_card_person
            )
        ORDER BY
            id
        LIMIT
            10000
    """
    return logsite_db().values(sql)

def process_log(log: str) -> List[Tuple[str, str]]:
    return re.findall(r'(\w+) (?:casts|plays) \[([^\]]+)\]', log, re.MULTILINE)

def init():
    sql = """
        CREATE TABLE IF NOT EXISTS _game_card_person (
            game_id INT NOT NULL,
            name NVARCHAR(100) NOT NULL,
            mtgo_username VARCHAR(50) NOT NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """
    logsite_db().execute(sql)
