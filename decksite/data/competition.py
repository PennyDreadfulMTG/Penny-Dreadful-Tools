from decksite import database

def get_or_insert_competition(start_date, end_date, name, competition_type):
    start = start_date.timestamp()
    end = end_date.timestamp()
    competition_type_id = type_id(competition_type)
    values = [start, end, name, competition_type_id]
    sql = """
        SELECT id
        FROM competition
        WHERE start_date = ? AND end_date = ? AND name = ? AND competition_type_id = ?
    """
    competition_id = database.Database().execute(sql, values)
    if competition_id:
        return competition_id
    sql = 'INSERT INTO competition (start_date, end_date, name, competition_type_id) VALUES (?, ?, ?, ?)'
    return database.Database().insert(sql, values)

def type_id(competition_type):
    sql = 'SELECT id FROM competition_type WHERE name = ?'
    return database.Database().value(sql, [competition_type])
