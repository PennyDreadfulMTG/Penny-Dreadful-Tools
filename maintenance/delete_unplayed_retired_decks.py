from decksite.database import db


def run():
    sql = """
        DELETE FROM
            deck
        WHERE
                retired
            AND
                updated_date < UNIX_TIMESTAMP(NOW() - INTERVAL 1 DAY)
            AND
                id NOT IN (SELECT deck_id FROM deck_match)
    """
    db().execute(sql)
