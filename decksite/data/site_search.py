import functools
from collections.abc import Iterable
from typing import Literal, NotRequired, TypedDict

from decksite.data import query
from decksite.database import db
from magic import fetcher, oracle
from shared.database import sqllikeescapesymbols

SearchResultType = Literal['Page', 'Archetype', 'Card', 'Person', 'Resource']


class SearchResult(TypedDict):
    name: str
    type: SearchResultType
    url: str
    search_name: NotRequired[str]


class CardNameMatch(TypedDict):
    name: str
    search_name: str


RESULT_LIMIT = 10

_TYPE_RANK: dict[SearchResultType, int] = {
    'Page': 0,
    'Archetype': 1,
    'Card': 2,
    'Person': 3,
    'Resource': 4,
}


def results(items: Iterable[SearchResult], search: str, limit: int = RESULT_LIMIT) -> list[SearchResult]:
    normalized_search = search.casefold()
    matches = (item for item in items if normalized_search in item.get('search_name', item['name']).casefold())
    return sorted(
        matches,
        key=lambda item: _result_rank(item, normalized_search),
    )[:limit]


def archetype_names(search: str, limit: int = RESULT_LIMIT) -> list[str]:
    return _database_names('name', 'archetype', search, limit)


def person_names(search: str, limit: int = RESULT_LIMIT) -> list[str]:
    person_name = query.person_query()
    return _database_names(person_name, 'person AS p', search, limit)


def card_names(search: str, limit: int = RESULT_LIMIT) -> list[CardNameMatch]:
    normalized_search = search.casefold()
    cards = oracle.cards_by_name()
    matches = [
        CardNameMatch(name=name, search_name=name)
        for name in cards
        if normalized_search in name.casefold()
    ]
    matches.extend(
        CardNameMatch(name=canonical_name, search_name=alias)
        for alias, canonical_name in card_aliases().items()
        if normalized_search in alias.casefold() and canonical_name in cards
    )
    ranked = sorted(matches, key=lambda match: _name_rank(match['search_name'], normalized_search))
    deduplicated = []
    seen = set()
    for match in ranked:
        if match['name'] in seen:
            continue
        seen.add(match['name'])
        deduplicated.append(match)
        if len(deduplicated) == limit:
            break
    return deduplicated


@functools.lru_cache(maxsize=1)
def card_aliases() -> dict[str, str]:
    return {alias: canonical_name for alias, canonical_name in fetcher.card_aliases()}


def _database_names(name_expression: str, table: str, search: str, limit: int) -> list[str]:
    escaped_search = sqllikeescapesymbols(search)
    contains = f'%{escaped_search}%'
    starts_with = f'{escaped_search}%'
    sql = f"""
        SELECT {name_expression} AS name
        FROM {table}
        WHERE {name_expression} IS NOT NULL AND {name_expression} LIKE %s
        ORDER BY
            CASE
                WHEN {name_expression} = %s THEN 0
                WHEN {name_expression} LIKE %s THEN 1
                ELSE 2
            END,
            CHAR_LENGTH({name_expression}),
            {name_expression}
        LIMIT %s
    """
    return [str(name) for name in db().values(sql, [contains, search, starts_with, limit])]


def _name_rank(name: str, normalized_search: str) -> tuple[int, int, str]:
    normalized_name = name.casefold()
    if normalized_name == normalized_search:
        match_rank = 0
    elif normalized_name.startswith(normalized_search):
        match_rank = 1
    else:
        match_rank = 2
    return match_rank, len(name), normalized_name


def _result_rank(item: SearchResult, normalized_search: str) -> tuple[int, int, int, str]:
    match_rank, length, normalized_name = _name_rank(item.get('search_name', item['name']), normalized_search)
    return match_rank, _TYPE_RANK[item['type']], length, normalized_name
