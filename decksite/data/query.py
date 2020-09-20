from typing import Dict, Optional, Union, cast

from decksite.deck_type import DeckType
from shared.database import sqlescape
from shared.pd_exception import InvalidArgumentException


def person_query(table: str = 'p') -> str:
    return 'LOWER(IFNULL(IFNULL(IFNULL({table}.name, {table}.mtgo_username), {table}.mtggoldfish_username), {table}.tappedout_username))'.format(table=table)

def competition_ids_by_type_select(competition_type: str) -> str:
    return """
        SELECT
            id
        FROM
            competition
        WHERE
            competition_series_id IN
                (
                    SELECT
                        id
                    FROM
                        competition_series
                    WHERE
                        competition_type_id
                    IN ({competition_type_id})
                )
        """.format(competition_type_id=competition_type_id_select(competition_type))

def competition_type_id_select(competition_type: str) -> str:
    return """
        SELECT
            id
        FROM
            competition_type
        WHERE
            name = '{competition_type}'
    """.format(competition_type=competition_type)

def competition_join() -> str:
    return """
        LEFT JOIN
            competition AS c ON d.competition_id = c.id
        LEFT JOIN
            competition_series AS cs ON cs.id = c.competition_series_id
        LEFT JOIN
            competition_type AS ct ON ct.id = cs.competition_type_id
    """

def season_query(season_id: Optional[Union[str, int]], column_name: str = 'season_id') -> str:
    if season_id is None or season_id == 'all' or season_id == 0:
        return 'TRUE'
    try:
        return '{column_name} = {season_id}'.format(column_name=column_name, season_id=int(season_id))
    except ValueError:
        raise InvalidArgumentException('No season with id `{season_id}`'.format(season_id=season_id))

def season_join() -> str:
    return """
        LEFT JOIN
            (
                SELECT
                    `start`.id,
                    `start`.code,
                    `start`.start_date AS start_date,
                    `end`.start_date AS end_date
                FROM
                    season AS `start`
                LEFT JOIN
                    season AS `end` ON `end`.id = `start`.id + 1
            ) AS season ON season.start_date <= d.created_date AND (season.end_date IS NULL OR season.end_date > d.created_date)
    """

def decks_order_by(sort_by: Optional[str], sort_order: Optional[str], competition_id: Optional[str]) -> str:
    if not sort_by and competition_id:
        sort_by = 'top8'
        sort_order = 'ASC'
    elif not sort_by:
        sort_by = 'date'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC'] # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    marginalia_order_by = """
        (CASE WHEN d.finish = 1 THEN 1
             WHEN d.finish = 2 AND c.top_n >= 2 THEN 2
             WHEN d.finish = 3 AND c.top_n >= 3 THEN 3
             WHEN cache.wins - 5 >= cache.losses THEN 4
             WHEN cache.wins - 3 >= cache.losses THEN 5
             WHEN d.finish = 5 AND c.top_n >= 5 THEN 6
             ELSE 99
         END)
    """
    sort_options = {
        'marginalia': marginalia_order_by,
        'colors': 'cache.color_sort',
        'name': 'cache.normalized_name',
        'person': person_query(),
        'archetype': 'a.name',
        'sourceName': 's.name',
        'record': f'(cache.wins - cache.losses) {sort_order}, cache.wins',
        'omw': 'cache.omw IS NOT NULL DESC, cache.omw',
        'top8': 'd.finish IS NOT NULL DESC, d.finish',
        'date': 'cache.active_date',
        'season': 'cache.active_date'
    }
    return sort_options[sort_by] + f' {sort_order}, d.finish ASC, cache.active_date DESC'

def cards_order_by(sort_by: Optional[str], sort_order: Optional[str]) -> str:
    if not sort_by:
        sort_by = 'numDecks'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC'] # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    sort_options = {
        'name': 'name',
        'numDecks': 'num_decks',
        'record': f'(SUM(wins) - SUM(losses)) {sort_order}, SUM(wins)',
        'winPercent': 'ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1)',
        'tournamentWins': 'tournament_wins',
        'tournamentTop8s': 'tournament_top8s',
        'perfectRuns': 'perfect_runs'
    }
    return sort_options[sort_by] + f' {sort_order}, num_decks DESC, record, name'

def exclude_active_league_runs(except_person_id: Optional[int]) -> str:
    clause = """
        d.retired
        OR
        IFNULL(ct.name, '') <> 'League'
        OR
        IFNULL(cache.wins, 0) + IFNULL(cache.draws, 0) + IFNULL(cache.losses, 0) >= 5
        OR
        c.end_date < UNIX_TIMESTAMP(NOW())
    """
    if except_person_id:
        clause += f'OR d.person_id = {except_person_id}'
    return clause

def decks_where(args: Dict[str, str], viewer_id: Optional[int]) -> str:
    parts = []
    parts.append(exclude_active_league_runs(viewer_id))
    if args.get('deckType') == DeckType.LEAGUE.value:
        parts.append("ct.name = 'League'")
    elif args.get('deckType') == DeckType.TOURNAMENT.value:
        parts.append("ct.name = 'Gatherling'")
    if args.get('archetypeId'):
        archetype_id = cast(int, args.get('archetypeId'))
        parts.append(archetype_where(archetype_id))
    if args.get('personId'):
        person_id = cast(int, args.get('personId'))
        parts.append(f'd.person_id = {person_id}')
    if args.get('cardName'):
        parts.append(card_where(cast(str, args.get('cardName'))))
    if args.get('competitionId'):
        competition_id = cast(int, args.get('competitionId'))
        parts.append(f'c.id = {competition_id}') # XSS for our cass now taht we don't use int()???
    return ') AND ('.join(parts)

def card_name_where(q: str) -> str:
    return "name LIKE '%%" + '%%'.join(c.replace("'", "''").replace('%', '%%') for c in list(q)) + "%%'"

def archetype_where(archetype_id: int) -> str:
    return f'd.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = {archetype_id})'

def card_where(name: str) -> str:
    return 'd.id IN (SELECT deck_id FROM deck_card WHERE card = {name})'.format(name=sqlescape(name))

def tournament_only_clause() -> str:
    return "ct.name = 'Gatherling'"
