def person_query(table='p'):
    return 'LOWER(IFNULL(IFNULL(IFNULL({table}.name, {table}.mtgo_username), {table}.mtggoldfish_username), {table}.tappedout_username))'.format(table=table)

def competition_ids_by_type_select(competition_type):
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

def competition_type_id_select(competition_type):
    return """
        SELECT
            id
        FROM
            competition_type
        WHERE
            name = '{competition_type}'
    """.format(competition_type=competition_type)

def competition_join():
    return """
        LEFT JOIN
            competition AS c ON d.competition_id = c.id
        LEFT JOIN
            competition_series AS cs ON cs.id = c.competition_series_id
        LEFT JOIN
            competition_type AS ct ON ct.id = cs.competition_type_id
    """
