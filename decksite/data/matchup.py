from typing import Dict, List, Union

from decksite.data import query
from decksite.database import db
from shared import guarantee

def matchup(hero: Dict[str, str], enemy: Dict[str, str], season_id: int = None) -> Dict[str, Union[str, int]]:
    where = 'TRUE'
    prefix = None
    args: List[Union[str, int]] = []
    if season_id:
        where += ' AND (season.id = %s)'
        args.append(season_id)
    for criteria in [hero, enemy]:
        prefix = '' if prefix is None else 'o'
        if criteria.get('person_id'):
            where += f' AND ({prefix}d.person_id = %s)'
            args.append(criteria['person_id'])
        if criteria.get('archetype_id'):
            where += f' AND ({prefix}d.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = %s))'
            args.append(criteria['archetype_id'])
        if criteria.get('card'):
            where += f' AND ({prefix}d.id IN (SELECT deck_id FROM deck_card WHERE card = %s))'
            args.append(criteria['card'])
    season_join = query.season_join()
    sql = f"""
        SELECT
            GROUP_CONCAT(d.id) AS hero_decks,
            GROUP_CONCAT(od.id) AS enemy_decks,
            GROUP_CONCAT(m.id) AS matches,
            IFNULL(SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END), 0) AS wins,
            IFNULL(SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END), 0) AS draws,
            IFNULL(SUM(CASE WHEN odm.games > dm.games THEN 1 ELSE 0 END), 0) AS losses
        FROM
            deck AS d
        LEFT JOIN
            deck_match AS dm ON dm.deck_id = d.id
        LEFT JOIN
            `match` AS m ON dm.match_id = m.id
        LEFT JOIN
            deck_match AS odm ON m.id = odm.match_id AND odm.deck_id <> d.id
        LEFT JOIN
            deck AS od ON odm.deck_id = od.id
        {season_join}
        WHERE
            {where}
    """
    return guarantee.exactly_one(db().select(sql, args))
