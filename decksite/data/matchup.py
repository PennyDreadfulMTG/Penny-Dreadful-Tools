from dataclasses import dataclass
from typing import Literal

from decksite.data import deck, match, person, query
from decksite.database import db
from magic.models import Deck
from shared import guarantee
from shared.container import Container
from shared.pd_exception import DoesNotExistException

MatchupOptionType = Literal['archetypes', 'people', 'cards']


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
    def win_percent(self) -> float | None:
        return round((self.wins / (self.wins + self.losses)) * 100, 1) if (self.wins + self.losses) > 0 else None


def search_options(option_type: MatchupOptionType, search: str, limit: int = 10, person_filter: person.PersonFilter = 'matchups') -> list[dict[str, str]]:
    """Return the small amount of data the matchup typeaheads actually use."""
    search = search.strip()
    if not search:
        return []
    contains = f'%{search}%'
    starts_with = f'{search}%'
    if option_type == 'archetypes':
        sql = """
            SELECT CAST(id AS CHAR) AS value, name
            FROM archetype
            WHERE name LIKE %s
            ORDER BY CASE WHEN name LIKE %s THEN 0 ELSE 1 END, name
            LIMIT %s
        """
    elif option_type == 'people':
        return person.search_options(search, limit, person_filter)
    else:
        # Match the old chooser's contents exactly: cards represented in the all-time
        # card statistics, rather than every card in the Oracle database.
        sql = """
            SELECT name AS value, name
            FROM (SELECT DISTINCT name FROM _card_stats) AS cards
            WHERE name LIKE %s
            ORDER BY CASE WHEN name LIKE %s THEN 0 ELSE 1 END, name
            LIMIT %s
        """
    return [{'value': str(r['value']), 'name': r['name']} for r in db().select(sql, [contains, starts_with, limit])]


def resolve_choices(choices: dict[str, str]) -> dict[str, str]:
    """Resolve submitted IDs (and typed-name fallbacks) into display-ready criteria."""
    resolved: dict[str, str] = {}
    archetype = _resolve_archetype(choices.get('archetype_id'), choices.get('archetype_name'))
    if archetype:
        resolved['archetype_id'] = str(archetype['id'])
        resolved['archetype_name'] = str(archetype['name'])
    person = _resolve_person(choices.get('person_id'), choices.get('person_name'))
    if person:
        resolved['person_id'] = str(person['id'])
        resolved['person_name'] = str(person['name'])
        resolved['person_label'] = str(person['label'])
    card_name = choices.get('card') or choices.get('card_name')
    if card_name:
        card = db().value('SELECT name FROM _card_stats WHERE name = %s LIMIT 1', [card_name])
        if card is None:
            raise DoesNotExistException(f'Did not find a played card with name of `{card_name}`')
        resolved['card'] = card
    return resolved


def _resolve_archetype(archetype_id: str | None, name: str | None) -> dict[str, str | int] | None:
    if archetype_id:
        rows = db().select('SELECT id, name FROM archetype WHERE id = %s', [archetype_id])
    elif name:
        rows = db().select('SELECT id, name FROM archetype WHERE name = %s', [name])
    else:
        return None
    if not rows:
        value = archetype_id or name
        raise DoesNotExistException(f'Did not find archetype `{value}`')
    return rows[0]


def _resolve_person(person_id: str | None, name: str | None) -> dict[str, str | int] | None:
    person_name = query.person_query()
    if person_id:
        rows = db().select(f'SELECT id, {person_name} AS name, LOWER(mtgo_username) AS label FROM person AS p WHERE id = %s AND mtgo_username IS NOT NULL', [person_id])
    elif name:
        rows = db().select(f'SELECT id, {person_name} AS name, LOWER(mtgo_username) AS label FROM person AS p WHERE mtgo_username = %s', [name])
    else:
        return None
    if not rows:
        value = person_id or name
        raise DoesNotExistException(f'Did not find MTGO player `{value}`')
    return rows[0]

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
    if hero_deck_ids:
        hero_decks = deck.load_decks('d.id IN (' + ', '.join(hero_deck_ids) + ')')
    else:
        hero_decks = []
    enemy_deck_ids = rs['enemy_deck_ids'].split(',') if rs['enemy_deck_ids'] else []
    match_ids = rs['match_ids'].split(',') if rs['match_ids'] else []
    if match_ids:
        ms = match.load_matches(where='m.id IN (' + ', '.join(match_ids) + ')', order_by='m.date DESC, m.round DESC')
    else:
        ms = []
    return MatchupResults(
        hero_deck_ids=hero_deck_ids,
        hero_decks=hero_decks,
        enemy_deck_ids=enemy_deck_ids,
        match_ids=match_ids,
        matches=ms,
        wins=rs['wins'],
        draws=rs['draws'],
        losses=rs['losses'],
    )
