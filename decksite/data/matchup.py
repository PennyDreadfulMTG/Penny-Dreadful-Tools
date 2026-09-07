from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from decksite.data import person, query
from decksite.database import db
from shared import guarantee
from shared.database import sqlescape
from shared.pd_exception import DoesNotExistException

MatchupOptionType = Literal['archetypes', 'people', 'cards']


@dataclass
class MatchupResults:
    num_decks: int
    num_matches: int
    wins: int
    draws: int
    losses: int

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

def matchup(hero: Mapping[str, str], enemy: Mapping[str, str], season_id: int | None = None) -> MatchupResults:
    where = matchup_where(hero, enemy)
    if season_id:
        where += f' AND (season.season_id = {sqlescape(season_id)})'
    season_join = query.season_join()
    sql = f"""
        SELECT
            COUNT(DISTINCT d.id) AS num_decks,
            COUNT(DISTINCT m.id) AS num_matches,
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
    rs = guarantee.exactly_one(db().select(sql))
    return MatchupResults(
        num_decks=rs['num_decks'],
        num_matches=rs['num_matches'],
        wins=rs['wins'],
        draws=rs['draws'],
        losses=rs['losses'],
    )


def opponent_decks_where(enemy: Mapping[str, str]) -> str:
    enemy_where = _criteria_where(enemy, 'matchup_enemy')
    return f"""
        EXISTS (
            SELECT 1
            FROM deck_match AS matchup_dm
            INNER JOIN deck_match AS matchup_odm ON matchup_odm.match_id = matchup_dm.match_id AND matchup_odm.deck_id <> matchup_dm.deck_id
            INNER JOIN deck AS matchup_enemy ON matchup_enemy.id = matchup_odm.deck_id
            WHERE matchup_dm.deck_id = d.id AND {enemy_where}
        )
    """


def matchup_where(hero: Mapping[str, str], enemy: Mapping[str, str]) -> str:
    return f"{_criteria_where(hero, 'd')} AND {_criteria_where(enemy, 'od')}"


def _criteria_where(criteria: Mapping[str, str], deck_alias: str) -> str:
    clauses = []
    if criteria.get('person_id'):
        clauses.append(f'{deck_alias}.person_id = {sqlescape(criteria["person_id"])}')
    if criteria.get('archetype_id'):
        clauses.append(f'{deck_alias}.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = {sqlescape(criteria["archetype_id"])})')
    if criteria.get('card'):
        clauses.append(f'{deck_alias}.id IN (SELECT deck_id FROM deck_card WHERE card = {sqlescape(criteria["card"])})')
    return ' AND '.join(clauses) or 'TRUE'
