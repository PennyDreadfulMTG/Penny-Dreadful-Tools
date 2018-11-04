from typing import List

from decksite.data import deck
from decksite.database import db
from magic.models import Deck
from shared.container import Container


def num_classified_decks() -> int:
    sql = 'SELECT COUNT(DISTINCT(deck_id)) AS c FROM ({apply_rules_query}) AS applied_rules'.format(apply_rules_query=apply_rules_query())
    return (db().select(sql))[0]['c']

def mistagged_decks() -> List[Deck]:
    sql = """SELECT deck_id, rule_archetype.name as rule_archetype_name, tagged_archetype.name as tagged_archetype_name
                FROM ({apply_rules_query}) AS applied_rules
                JOIN deck on applied_rules.deck_id = deck.id
                join archetype as rule_archetype on rule_archetype.id = applied_rules.archetype_id
                join archetype as tagged_archetype on tagged_archetype.id = deck.archetype_id
                WHERE rule_archetype.id != tagged_archetype.id""".format(apply_rules_query=apply_rules_query())
    deck_ids: List[str] = []
    rule_archetypes = {}
    for r in (Container(row) for row in db().select(sql)):
        deck_ids.append(str(r.deck_id))
        rule_archetypes[r.deck_id] = r.rule_archetype_name
    result = deck.load_decks(where='d.id IN ('+','.join(deck_ids)+')')
    for d in result:
        d.rule_archetype_name = rule_archetypes[d.id]
    return result

def doubled_decks() -> List[Deck]:
    sql = """SELECT deck_id, GROUP_CONCAT(archetype.name) AS concat_archetypes
                FROM ({apply_rules_query}) AS applied_rules
                JOIN archetype ON applied_rules.archetype_id = archetype.id
                GROUP BY deck_id
                HAVING COUNT(DISTINCT archetype.id) > 1""".format(apply_rules_query=apply_rules_query())
    deck_ids: List[str] = []
    concat_archetypes = {}
    for r in (Container(row) for row in db().select(sql)):
        deck_ids.append(str(r.deck_id))
        concat_archetypes[r.deck_id] = r.concat_archetypes
    result = deck.load_decks(where='d.id IN ('+','.join(deck_ids)+')')
    for d in result:
        d.concat_archetypes = concat_archetypes[d.id]
    return result

# Currently we do this query several times in a row, but at least with a small number of rules it's cheap enough not to matter
def apply_rules_query(deck_query: str = '1 = 1'):
    return f"""
with rule_card_count as
(
select rule.id, count(card) as card_count from rule join rule_card on rule.id = rule_card.rule_id where rule_card.include = TRUE group by rule.id
),
candidates as
(select deck.id as deck_id,
 count(distinct deck_card.card) as included_count,
 max(rule_card_count.card_count) as required_count,-- fake MAX
 rule.id as rule_id
from deck
 join deck_card on deck.id = deck_card.deck_id
 join (SELECT * from rule_card where include = TRUE) as inclusions on deck_card.card = inclusions.card
 join rule on rule.id = inclusions.rule_id
 join rule_card_count on rule.id = rule_card_count.id
 where {deck_query}
group by deck.id, rule.id
having included_count = required_count)
select candidates.deck_id, candidates.rule_id, suggested_archetype.id as archetype_id from candidates
 join rule on candidates.rule_id = rule.id
 join archetype as suggested_archetype on rule.archetype_id = suggested_archetype.id
 left join (select * from rule_card where include = FALSE) as exclusions on candidates.rule_id = exclusions.rule_id
 left join deck_card on candidates.deck_id = deck_card.deck_id and exclusions.card = deck_card.card
group by candidates.deck_id, candidates.rule_id
having count(deck_card.card) = 0"""
