from typing import Dict, List, Tuple

from decksite.data import deck
from decksite.database import db
from magic.models import Deck
from shared.container import Container


def apply_rules_to_decks(decks: List[Deck]) -> None:
    if len(decks) == 0:
        return
    decks_by_id = {}
    for d in decks:
        decks_by_id[d.id] = d
    id_list = ', '.join(str(d.id) for d in decks)
    sql = """
            SELECT
                deck_id,
                archetype_name
            FROM
                ({apply_rules_query}) AS applied_rules
            GROUP BY
                deck_id
            HAVING
                COUNT(DISTINCT archetype_id) = 1
        """.format(apply_rules_query=apply_rules_query(f'deck_id IN ({id_list})'))
    for r in (Container(row) for row in db().select(sql)):
        decks_by_id[r.deck_id].rule_archetype_name = r.archetype_name

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
    rule_archetypes = {}
    for r in (Container(row) for row in db().select(sql)):
        rule_archetypes[r.deck_id] = r.rule_archetype_name
    if not rule_archetypes:
        return []
    ids_list = ', '.join(str(deck_id) for deck_id in rule_archetypes)
    result = deck.load_decks(where=f'd.id IN ({ids_list})')
    for d in result:
        d.rule_archetype_name = rule_archetypes[d.id]
    return result

def doubled_decks() -> List[Deck]:
    sql = """
        SELECT
            deck_id,
            GROUP_CONCAT(archetype_id) AS archetype_ids,
            GROUP_CONCAT(archetype_name SEPARATOR '|') AS archetype_names
        FROM
            ({apply_rules_query}) AS applied_rules
        GROUP BY
            deck_id
        HAVING
            COUNT(DISTINCT archetype_id) > 1
        """.format(apply_rules_query=apply_rules_query())
    archetypes_from_rules: Dict[int, List[Container]]
    for r in [Container(row) for row in db().select(sql)]:
        matching_archetypes = zip(r.archetype_ids.split(','), r.archetype_names.split('|'))
        archetypes_from_rules[r.deck_id] = [Container({'archetype_id': archetype_id, 'archetype_name': archetype_name}) for archetype_id, archetype_name in matching_archetypes]
    if not archetypes_from_rules:
        return []
    ids_list = ', '.join(str(deck_id) for deck_id in archetypes_from_rules)
    result = deck.load_decks(where=f'd.id IN ({ids_list})')
    for d in result:
        d.archetypes_from_rules = archetypes_from_rules[d.id]
    return result

def overlooked_decks() -> List[Deck]:
    sql = """
            SELECT
                deck.id as deck_id
            FROM
                deck
            LEFT JOIN
                ({apply_rules_query}) AS applied_rules
            ON
                deck.id = applied_rules.deck_id
            WHERE
                applied_rules.rule_id IS NULL AND deck.archetype_id IN
                    (
                        SELECT
                            DISTINCT archetype_id
                        FROM
                            rule
                    )
            """.format(apply_rules_query=apply_rules_query())
    deck_ids = [str(row['deck_id']) for row in db().select(sql)]
    if not deck_ids:
        return []
    ids_list = ', '.join(deck_ids)
    return deck.load_decks(where=f'd.id IN ({ids_list})')

def load_all_rules() -> List[Container]:
    result = []
    result_by_id = {}
    sql = """
        SELECT
            rule.id AS id,
            archetype.id AS archetype_id,
            archetype.name AS archetype_name,
            COUNT(DISTINCT applied_rules.deck_id) as num_decks
        FROM
            rule
        INNER JOIN
            archetype
        ON
            rule.archetype_id = archetype.id
        LEFT JOIN
            ({apply_rules_query}) AS applied_rules
        ON
            rule.id = applied_rules.rule_id
        GROUP BY
            id
        """.format(apply_rules_query=apply_rules_query())
    for r in (Container(row) for row in db().select(sql)):
        result.append(r)
        result_by_id[r.id] = r
        r.included_cards = []
        r.excluded_cards = []
    sql = 'SELECT rule_id, card, n, include FROM rule_card'
    for r in (Container(row) for row in db().select(sql)):
        if r.include:
            result_by_id[r.rule_id].included_cards.append({'n': r.n, 'card': r.card})
        else:
            result_by_id[r.rule_id].excluded_cards.append({'n': r.n, 'card': r.card})
    return result

def add_rule(archetype_id: int) -> None:
    sql = 'INSERT INTO rule (archetype_id) VALUES (%s)'
    db().insert(sql, [archetype_id])

def update_cards(rule_id: int, inc: List[Tuple[int, str]], exc: List[Tuple[int, str]]) -> None:
    db().begin('update_rule_cards')
    sql = 'DELETE FROM rule_card WHERE rule_id = %s'
    db().execute(sql, [rule_id])
    for n, card in inc:
        sql = 'INSERT INTO rule_card (rule_id, card, n, include) VALUES (%s, %s, %s, TRUE)'
        db().execute(sql, [rule_id, card, n])
    for n, card in exc:
        sql = 'INSERT INTO rule_card (rule_id, card, n, include) VALUES (%s, %s, %s, FALSE)'
        db().execute(sql, [rule_id, card, n])
    db().commit('update_rule_cards')

# Currently we do this query several times in a row, but at least with a small number of rules it's cheap enough not to matter
def apply_rules_query(deck_query: str = '1 = 1') -> str:
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
                deck_card.sideboard = FALSE AND deck_card.n >= inclusions.n AND {deck_query}
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
        INNER JOIN
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
            candidates.deck_id = deck_card.deck_id AND exclusions.card = deck_card.card AND deck_card.n >= exclusions.n
        GROUP BY
            candidates.deck_id, rule_id
        HAVING
            COUNT(deck_card.card) = 0
    """
