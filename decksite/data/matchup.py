from dataclasses import dataclass

from decksite.data import deck, match, query
from decksite.database import db
from magic.models import Deck
from shared import guarantee
from shared.container import Container


@dataclass
class MatchupResults:
    hero_deck_ids: list[int]
    enemy_deck_ids: list[int]
    match_ids: list[int]
    wins: int
    draws: int
    losses: int
    hero_decks: list[Deck]
    matches: list[Container]

    @property
    def num_decks(self) -> int:
        return len(self.hero_deck_ids)

    @property
    def win_percent(self) -> str:
        return str(round((self.wins / (self.wins + self.losses)) * 100, 1)) if (self.wins + self.losses) > 0 else ''

def matchup(hero: dict[str, str], enemy: dict[str, str], season_id: int | None = None) -> MatchupResults:
    where = 'TRUE'
    prefix = None
    args: list[str | int] = []
    if season_id:
        where += ' AND (season.season_id = %s)'
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
            GROUP_CONCAT(DISTINCT d.id) AS hero_deck_ids,
            GROUP_CONCAT(DISTINCT od.id) AS enemy_deck_ids,
            GROUP_CONCAT(DISTINCT m.id) AS match_ids,
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
    rs = guarantee.exactly_one(db().select(sql, args))
    hero_deck_ids = rs['hero_deck_ids'].split(',') if rs['hero_deck_ids'] else []
    match_ids = rs['match_ids'].split(',') if rs['match_ids'] else []
    if match_ids:
        ms, _ = match.load_matches(where='m.id IN (' + ', '.join(match_ids) + ')', order_by='m.date DESC, m.round DESC')
    else:
        ms = []
    return MatchupResults(
        hero_deck_ids=hero_deck_ids,
        hero_decks=deck.load_decks('d.id IN (' + ', '.join(hero_deck_ids) + ')') if hero_deck_ids else [],
        enemy_deck_ids=rs['enemy_deck_ids'].split(',') if rs['enemy_deck_ids'] else [],
        match_ids=rs['match_ids'].split(',') if rs['match_ids'] else [],
        matches=ms,
        wins=rs['wins'],
        draws=rs['draws'],
        losses=rs['losses'],
    )
