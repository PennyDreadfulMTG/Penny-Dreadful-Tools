from decksite.deck_type import DeckType
from find import search
from shared.database import sqlescape
from shared.pd_exception import InvalidArgumentException

DEFAULT_LIVE_TABLE_PAGE_SIZE = 20
MAX_LIVE_TABLE_PAGE_SIZE = 500

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

def season_query(season_id: str | int | None, column_name: str = 'season_id') -> str:
    if season_id is None or season_id == 'all' or season_id == 0:
        return 'TRUE'
    try:
        return f'{column_name} = {int(season_id)}'
    except ValueError as c:
        raise InvalidArgumentException(f'No season with id `{season_id}`') from c

def season_join() -> str:
    return 'LEFT JOIN deck_cache AS season ON d.id = season.deck_id'

def decks_order_by(sort_by: str | None, sort_order: str | None, competition_id: str | None) -> str:
    if not sort_by and competition_id:
        sort_by = 'top8'
        sort_order = 'ASC'
    elif not sort_by:
        sort_by = 'date'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC']  # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
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
        'season': 'cache.active_date',
    }
    return sort_options[sort_by] + f' {sort_order}, d.finish ASC, cache.active_date DESC'

def cards_order_by(sort_by: str | None, sort_order: str | None) -> str:
    if not sort_by:
        sort_by = 'numDecks'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC']  # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    sort_options = {
        'name': 'name',
        'numDecks': 'num_decks',
        'record': f'record {sort_order}, wins',
        'winPercent': 'ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1)',
        'tournamentWins': 'tournament_wins',
        'tournamentTop8s': 'tournament_top8s',
        'perfectRuns': 'perfect_runs',
    }
    return sort_options[sort_by] + f' {sort_order}, num_decks DESC, record, name'

def people_order_by(sort_by: str | None, sort_order: str | None) -> str:
    if not sort_by:
        sort_by = 'numDecks'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC']  # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    sort_options = {
        'elo': 'elo',
        'name': 'name',
        'numDecks': 'num_decks',
        'record': f'(SUM(dc.wins) - SUM(dc.losses)) {sort_order}, SUM(dc.wins)',
        'winPercent': 'ROUND((SUM(dc.wins) / NULLIF(SUM(dc.wins + dc.losses), 0)) * 100, 1)',
        'tournamentWins': 'tournament_wins',
        'tournamentTop8s': 'tournament_top8s',
        'perfectRuns': 'perfect_runs',
    }
    return sort_options[sort_by] + f' {sort_order}, num_decks DESC, record, name'

def head_to_head_order_by(sort_by: str | None, sort_order: str | None) -> str:
    if not sort_by:
        sort_by = 'numMatches'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC']  # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    sort_options = {
        'name': 'opp_mtgo_username',
        'numMatches': 'num_matches',
        'record': f'(SUM(wins) - SUM(losses)) {sort_order}, SUM(wins)',
        'winPercent': 'ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1)',
    }
    return sort_options[sort_by] + f' {sort_order}, num_matches DESC, record, name'

def leaderboard_order_by(sort_by: str | None, sort_order: str | None) -> str:
    if not sort_by:
        sort_by = 'points'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC']  # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    sort_options = {
        'name': 'person',
        'numDecks': 'num_decks',
        'wins': 'wins',
        'points': 'points',
    }
    return sort_options[sort_by] + f' {sort_order}, points DESC, wins DESC, person'

def matches_order_by(sort_by: str | None, sort_order: str | None) -> str:
    if not sort_by:
        sort_by = 'date'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC']  # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    sort_options = {
        'date': 'date',
        'person': 'person',
        'deckName': 'deck_name',
        'mtgoId': 'mtgo_id',
        'opponent': 'opponent',
        'opponentDeckName': 'opponent_deck_name',
    }
    return sort_options[sort_by] + f' {sort_order}, person'

def exclude_active_league_runs(except_person_id: int | None) -> str:
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

def decks_where(args: dict[str, str], is_admin: bool, viewer_id: int | None) -> str:
    parts = ['TRUE']
    if not is_admin:
        parts.append(exclude_active_league_runs(viewer_id))
    if args.get('deckType') == DeckType.LEAGUE.value:
        parts.append("ct.name = 'League'")
    elif args.get('deckType') == DeckType.TOURNAMENT.value:
        parts.append("ct.name = 'Gatherling'")
    if args.get('archetypeId'):
        archetype_id = int(args.get('archetypeId', ''))
        parts.append(archetype_where(archetype_id))
    if args.get('personId'):
        person_id = int(args.get('personId', ''))
        parts.append(f'd.person_id = {person_id}')
    if args.get('cardName'):
        parts.append(card_where(args.get('cardName', '')))
    if args.get('competitionId'):
        competition_id = int(args.get('competitionId', ''))
        parts.append(f'c.id = {competition_id}')
    return ') AND ('.join(parts)

def text_match_where(field: str, q: str) -> str:
    return f"{field} LIKE '%%" + '%%'.join(c.replace("'", "''").replace('%', '%%') for c in list(q)) + "%%'"

def archetype_where(archetype_id: int) -> str:
    return f'd.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = {archetype_id})'

def card_where(name: str) -> str:
    return f'd.id IN (SELECT deck_id FROM deck_card WHERE card = {sqlescape(name)})'

# Returns two values, a SQL WHERE clause and a message about that clause (possibly an error message) suitable for display.
def card_search_where(q: str) -> tuple[str, str]:
    try:
        cs = search.search(q)
        return 'FALSE' if len(cs) == 0 else 'name IN (' + ', '.join(sqlescape(c.name) for c in cs) + ')', ''
    except search.InvalidSearchException as e:
        return 'FALSE', str(e)

def tournament_only_clause() -> str:
    return "ct.name = 'Gatherling'"

def decks_updated_since(ts: int) -> str:
    return f'(q.changed_date > {ts} OR d.updated_date > {ts})'

def pagination(args: dict[str, str]) -> tuple[int, int, str]:
    try:
        page_size = int(args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
        page = int(args.get('page', 0))
    except ValueError as e:
        raise InvalidArgumentException from e
    if page_size > MAX_LIVE_TABLE_PAGE_SIZE:
        raise InvalidArgumentException(f'Page size of {page_size} greater than maximum of {MAX_LIVE_TABLE_PAGE_SIZE}')
    start = page * page_size
    return page, page_size, f'LIMIT {start}, {page_size}'
