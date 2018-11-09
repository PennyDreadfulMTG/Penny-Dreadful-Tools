from typing import List

from decksite.data import deck
from decksite.database import db
from magic.models import Deck
from shared.container import Container


def num_classified_decks() -> int:
    sql = 'SELECT COUNT(DISTINCT(deck_id)) AS c FROM ({apply_rules_query}) AS applied_rules'.format(apply_rules_query=apply_rules_query())
    return db().value(sql)

def mistagged_decks() -> List[Deck]:
    sql = """
            SELECT
                deck_id,
                rule_archetype.name AS rule_archetype_name,
                tagged_archetype.name AS tagged_archetype_name
            FROM
                ({apply_rules_query}) AS applied_rules
            INNER JOIN
                deck
            ON
                applied_rules.deck_id = deck.id
            INNER JOIN
                archetype AS rule_archetype
            ON
                rule_archetype.id = applied_rules.archetype_id
            INNER JOIN
                archetype AS tagged_archetype
            ON
                tagged_archetype.id = deck.archetype_id
            WHERE
                rule_archetype.id != tagged_archetype.id
            """.format(apply_rules_query=apply_rules_query())
    deck_ids: List[str] = []
    rule_archetypes = {}
    for r in (Container(row) for row in db().select(sql)):
        deck_ids.append(str(r.deck_id))
        rule_archetypes[r.deck_id] = r.rule_archetype_name
    if len(deck_ids) == 0:
        return []
    ids_list = ', '.join(deck_ids)
    result = deck.load_decks(where=f'd.id IN ({ids_list})')
    for d in result:
        d.rule_archetype_name = rule_archetypes[d.id]
    return result

def doubled_decks() -> List[Deck]:
    sql = """
            SELECT
                deck_id,
                GROUP_CONCAT(archetype_name) AS concat_archetypes
            FROM
                ({apply_rules_query}) AS applied_rules
            GROUP BY
                deck_id
            HAVING
                COUNT(DISTINCT archetype_id) > 1
            """.format(apply_rules_query=apply_rules_query())
    deck_ids: List[str] = []
    concat_archetypes = {}
    for r in (Container(row) for row in db().select(sql)):
        deck_ids.append(str(r.deck_id))
        concat_archetypes[r.deck_id] = r.concat_archetypes
    if len(deck_ids) == 0:
        return []
    ids_list = ', '.join(deck_ids)
    result = deck.load_decks(where=f'd.id IN ({ids_list})')
    for d in result:
        d.concat_archetypes = concat_archetypes[d.id]
    return result

def load_all_rules() -> List[Container]:
    result = []
    result_by_id = {}
    sql = """
        SELECT
            rule_id AS id,
            archetype_id,
            archetype_name,
            COUNT(DISTINCT deck_id) as num_decks
        FROM
            ({apply_rules_query}) AS applied_rules
        GROUP BY
            rule_id
        """.format(apply_rules_query=apply_rules_query(include_all_rules=True))
    for r in (Container(row) for row in db().select(sql)):
        result.append(r)
        result_by_id[r.id] = r
        r.included_cards = []
        r.excluded_cards = []
    sql = 'SELECT rule_id, card, include FROM rule_card'
    for r in (Container(row) for row in db().select(sql)):
        if r.include:
            result_by_id[r.rule_id].included_cards.append(r.card)
        else:
            result_by_id[r.rule_id].excluded_cards.append(r.card)
    return result

def add_rule(archetype_id: int) -> None:
    sql = 'INSERT INTO rule (archetype_id) VALUES (%s)'
    db().insert(sql, [archetype_id])

def update_cards(rule_id: int, inc: str, exc: str) -> None:
    db().begin('update_rule_cards')
    sql = 'DELETE FROM rule_card WHERE rule_id = %s'
    db().execute(sql, [rule_id])
    for card in inc:
        sql = 'INSERT INTO rule_card (rule_id, card, include) VALUES (%s, %s, TRUE)'
        db().execute(sql, [rule_id, card])
    for card in exc:
        sql = 'INSERT INTO rule_card (rule_id, card, include) VALUES (%s, %s, FALSE)'
        db().execute(sql, [rule_id, card])
    db().commit('update_rule_cards')

# Currently we do this query several times in a row, but at least with a small number of rules it's cheap enough not to matter
def apply_rules_query(deck_query: str = '1 = 1', include_all_rules: bool = False) -> str:
    join_type = 'RIGHT' if include_all_rules else 'INNER'
    return f"""
        WITH rule_card_count AS
        (
            SELECT
                rule.id, COUNT(card) AS card_count
            FROM
                rule
            JOIN
                rule_card
            ON
                rule.id = rule_card.rule_id
            WHERE
                rule_card.include = TRUE
            GROUP BY
                rule.id
        ),
        candidates AS
        (
            SELECT
                deck.id AS deck_id,
                COUNT(DISTINCT deck_card.card) AS included_count,
                MAX(rule_card_count.card_count) AS required_count,-- fake MAX due to aggregate function
                rule.id AS rule_id
            FROM
                deck
            JOIN
                deck_card
            ON
                deck.id = deck_card.deck_id
            JOIN
                (
                    SELECT
                        *
                    FROM
                        rule_card
                    WHERE
                        include = TRUE
                ) AS inclusions
            ON
                deck_card.card = inclusions.card
            JOIN
                rule
            ON
                rule.id = inclusions.rule_id
            JOIN
                rule_card_count
            ON
                rule.id = rule_card_count.id
            WHERE
                deck_card.sideboard = FALSE AND {deck_query}
            GROUP BY
                deck.id, rule.id
            HAVING
                included_count = required_count
        )
        SELECT
            candidates.deck_id,
            rule.id AS rule_id,
            suggested_archetype.id AS archetype_id,
            suggested_archetype.name AS archetype_name
        FROM
            candidates
        {join_type} JOIN
            rule
        ON
            candidates.rule_id = rule.id
        JOIN
            archetype AS suggested_archetype
        ON
            rule.archetype_id = suggested_archetype.id
        LEFT JOIN
            (
                SELECT
                    *
                FROM
                    rule_card
                WHERE
                    include = FALSE
            ) AS exclusions
        ON
            candidates.rule_id = exclusions.rule_id
        LEFT JOIN
            deck_card
        ON
            candidates.deck_id = deck_card.deck_id AND exclusions.card = deck_card.card
        GROUP BY
            candidates.deck_id, candidates.rule_id
        HAVING
            COUNT(deck_card.card) = 0
    """
