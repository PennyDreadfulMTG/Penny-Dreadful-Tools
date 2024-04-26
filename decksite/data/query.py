from shared.pd_exception import InvalidArgumentException

# Repeated snippets of SQL used in various parts of decksite.data. Should not touch the database, text-only.
# If you need to make a query to form your SQL, see the clauses module.

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

def ranks_select() -> str:
    return """
        SELECT
            name,
            CASE
                WHEN playability = 0 THEN NULL
                ELSE ROW_NUMBER() OVER (ORDER BY playability DESC)
            END AS rank
        FROM
            _playability
    """
