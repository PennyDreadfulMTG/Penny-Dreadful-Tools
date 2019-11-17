import re
from typing import List, Tuple

from decksite.data import preaggregation, query
from decksite.database import db as decksite_db
from logsite.database import db as logsite_db
from magic.models.card import Card
from shared import configuration
from shared.database import sqlescape
from shared.decorators import retry_after_calling


def preaggregate():
    preaggregate_played_cards_by_person()

def preaggregate_played_cards_by_person():
    table = '_played_card_person_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            person_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            PRIMARY KEY (season_id, person_id, name),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id)  ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            gcp.name,
            season.id AS season_id,
            p.id AS person_id,
            SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws
        FROM
            {logsite_database}._game_card_person AS gcp
        INNER JOIN
            person AS p ON gcp.mtgo_username = p.mtgo_username
        INNER JOIN
            {logsite_database}.game AS g ON g.id = gcp.game_id
        INNER JOIN
            `match` AS m ON m.mtgo_id = g.match_id
        INNER JOIN
            deck_match AS dm ON dm.match_id = m.id AND dm.deck_id IN (SELECT id FROM deck WHERE person_id = p.id)
        INNER JOIN
            deck_match AS odm ON odm.match_id = m.id AND odm.deck_id NOT IN (SELECT id FROM deck WHERE person_id = p.id)
        INNER JOIN
            deck AS d ON dm.deck_id = d.id
        {season_join}
    """.format(table=table, logsite_database=configuration.get('logsite_database'), season_join=query.season_join())
    print(sql)
    preaggregation.preaggregate(table, sql)

@retry_after_calling(preaggregate_played_cards_by_person)
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
    """
    logsite_db().select(sql)

def process_logs() -> None:
    init()
    sql = 'SELECT id AS game_id, log FROM game WHERE id NOT IN (SELECT game_id FROM _game_card_person) LIMIT 1000'
    rs = logsite_db().select(sql)
    values = []
    for r in rs:
        entries = process_log(r['log'])
        for entry in entries:
            values.append([r['game_id']] + list(entry))
    sql = 'INSERT INTO _game_card_person (game_id, mtgo_username, name) VALUES '
    sql += ', '.join('(' + ', '.join(str(sqlescape(v)) for v in vs) + ')' for vs in values)
    logsite_db().execute(sql)

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
