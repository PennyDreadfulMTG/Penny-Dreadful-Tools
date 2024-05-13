from scipy.stats import norm

from decksite.data import achievements
from decksite.data.query import person_query
from decksite.deck_type import DeckType
from decksite.tournament import CompetitionFlag
from find import search
from magic import rotation
from shared.database import sqlescape
from shared.pd_exception import InvalidArgumentException

# Form SQL WHERE, ORDER BY and LIMIT clauses, sometimes by making db queries.

DEFAULT_LIVE_TABLE_PAGE_SIZE = 20
MAX_LIVE_TABLE_PAGE_SIZE = 500

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

def rotation_order_by(sort_by: str | None, sort_order: str | None) -> str:
    if not sort_by:
        sort_by = 'hitInLastRun'
        sort_order = 'ASC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    assert sort_order in ['ASC', 'DESC']  # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    order_by_rank = 'rank IS NULL ASC, rank ASC, name ASC'
    if sort_by == 'hitInLastRun':
        return f"""
            CASE
                WHEN status = 'Undecided' THEN 0
                WHEN status = 'Legal' THEN 1
                ELSE 2
            END {sort_order},
            CASE
                WHEN status = 'Undecided' THEN -hits
                WHEN status = 'Legal' THEN hits
                ELSE hits
            END {sort_order},
            hit_in_last_run DESC,
            {order_by_rank}
        """
    if sort_by == 'rank':
        return f"rank IS NULL {sort_order}, rank {sort_order}, IF(status = 'Legal', hits, {rotation.TOTAL_RUNS}) ASC, hits DESC, name ASC"
    sort_options = {
        'name': 'name',
        'hits': 'hits',
        'hitsNeeded': 'hits_needed',
    }
    return sort_options[sort_by] + f' {sort_order}, {order_by_rank}'

def archetype_order_by(sort_by: str | None, sort_order: str | None) -> str:
    if not sort_by:
        sort_by = 'quality'
        sort_order = 'DESC'
    else:
        sort_by = str(sort_by)
        sort_order = str(sort_order)
    sort_options = {
        'name': ('name', 'ASC'),
        'metaShare': ('SUM(wins + losses + draws) / SUM(SUM(wins + losses + draws)) OVER ()', 'DESC'),
        'quality': (wilson_lower_bound_sql(), 'DESC'),
        'winPercent': ('SUM(wins) / NULLIF(SUM(wins + losses), 0)', 'DESC'),
        'tournamentWins': ('tournament_wins', 'DESC'),
        'tournamentTop8s': ('tournament_top8s', 'DESC'),
        'perfectRuns': ('perfect_runs', 'DESC'),
    }
    col, default_order = sort_options[sort_by]
    if sort_order == 'AUTO':
        sort_order = default_order
    assert sort_order in ['ASC', 'DESC']  # This is a form of SQL injection protection so don't remove it just because you don't like asserts in prod without replacing it with something.
    return f'{col} {sort_order}, {wilson_lower_bound_sql()} DESC, num_decks DESC, win_percent DESC, name ASC'

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
    person_id = None
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
    if args.get('cardName'):
        parts.append(card_where(args.get('cardName', '')))
    if args.get('competitionFlagId'):
        competition_flag_id = CompetitionFlag(int(args.get('competitionFlagId', ''))).value
        parts.append(f'c.competition_flag_id = {competition_flag_id} AND d.finish = 1')
    if args.get('competitionId'):
        competition_id = int(args.get('competitionId', ''))
        parts.append(f'c.id = {competition_id}')
    if args.get('achievementKey'):
        achievement_key = str(args.get('achievementKey'))
        achievement_person_id = int(args.get('personId', ''))
        season_id = int(args.get('seasonId', ''))
        deck_ids = achievements.load_deck_ids(achievement_key, achievement_person_id, season_id)
        # Some achievements load decks from multiple people by id …
        if deck_ids:
            parts.append(f"d.id IN ({', '.join(map(str, deck_ids))})")
            person_id = None
        # … but the other should be filtered to this person's decks
        else:
            person_id = achievement_person_id
    if person_id:
        parts.append(f'd.person_id = {person_id}')

    return ') AND ('.join(parts)

def text_where(field: str, q: str) -> str:
    return f"{field} LIKE '%%" + q.replace("'", "''").replace('%', '%%') + "%%'"

def text_match_where(field: str, q: str) -> str:
    return f"{field} LIKE '%%" + '%%'.join(c.replace("'", "''").replace('%', '%%') for c in list(q)) + "%%'"

def archetype_where(archetype_id: int) -> str:
    return f'd.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = {archetype_id})'

def card_where(name: str) -> str:
    return f'd.id IN (SELECT deck_id FROM deck_card WHERE card = {sqlescape(name)})'

# Returns two values, a SQL WHERE clause and a message about that clause (possibly an error message) suitable for display.
def card_search_where(q: str, base_query: str | None = None, column_name: str = 'name') -> tuple[str, str]:
    try:
        query = f'({q})' if q else ''
        query += ' AND ' if q and base_query else ''
        query += f'({base_query})' if base_query else ''
        cs = search.search(query)
        return 'FALSE' if len(cs) == 0 else f'{column_name} IN (' + ', '.join(sqlescape(name) for name in cs) + ')', ''
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


VERY_HIGH_CONFIDENCE = 0.99
HIGH_CONFIDENCE = 0.95

# Calculate the lower using the Wilson interval at 95% confidence.
# See https://discord.com/channels/207281932214599682/230056266938974218/691464882998214686
# See https://stackoverflow.com/a/10029645/375262
# See https://www.evanmiller.org/how-not-to-sort-by-average-rating.html
def wilson_lower_bound_sql(phat: str = 'SUM(wins) / SUM(wins + losses)', n: str = 'SUM(wins + losses)', confidence_level: float = VERY_HIGH_CONFIDENCE) -> str:
    z = z_value(confidence_level)
    return f'({phat} + {z} * {z} / (2 * {n}) - {z} * SQRT(({phat} * (1 - {phat}) + {z} * {z} / (4 * {n})) / {n})) / (1 + {z} * {z} / {n})'

def z_value(confidence_level: float) -> float:
    return norm.ppf((1 + confidence_level) / 2)
