import re
from typing import List, Tuple

from magic.models.card import Card
from shared.decorators import retry_after_calling

# BAKERT need a scheduled job to process the logs into the first table(s) to preaggregate from.

def preaggregate_played_cards_by_person():
    table = '_played_card_person_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            person_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL
            PRIMARY KEY (season_id, person_id, name),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id)  ON UPDATE CASCADE ON DELETE CASCADE,
            INDEX idx_person_id_name (person_id, name)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT

    """
    preaggregate(table, sql)

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
    db().select(sql)

def process_logs() -> None:
    sql = 'SELECT id AS game_id, log FROM game WHERE id NOT IN (SELECT game_id FROM _match_card_played)'
    rs = db().select(sql, [highest_id])
    for r in rs:
        values = [r['game_id']] + process_log(r['log'])
    sql = 'INSERT INTO _match_card_played (game_id, card, mtgo_username) VALUES '
    sql += ', '.join('(' + ', '.join(vs) + ')' for vs in values)
    db().execute(sql)

def process_log(log: str) -> List[Tuple[str, str]]:
    return re.findall(r'(\w+) (?:casts|plays) \[([^\]]+)\]', log, re.MULTILINE)
