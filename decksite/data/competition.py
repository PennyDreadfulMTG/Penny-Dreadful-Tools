from munch import Munch

from shared.database import sqlescape
from shared import dtutil

from decksite.database import db

def get_or_insert_competition(start_date, end_date, name, competition_type, url):
    start = start_date.timestamp()
    end = end_date.timestamp()
    competition_type_id = type_id(competition_type)
    values = [start, end, name, competition_type_id, url]
    sql = """
        SELECT id
        FROM competition
        WHERE start_date = ? AND end_date = ? AND name = ? AND competition_type_id = ? AND url = ?
    """
    competition_id = db().value(sql, values)
    if competition_id:
        return competition_id
    sql = 'INSERT INTO competition (start_date, end_date, name, competition_type_id, url) VALUES (?, ?, ?, ?, ?)'
    return db().insert(sql, values)

def type_id(competition_type):
    sql = 'SELECT id FROM competition_type WHERE name = ?'
    return db().value(sql, [competition_type])

def load_competition(competition_id):
    return load_competitions('id = {competition_id}'.format(competition_id=sqlescape(competition_id)))[0]

def load_competitions(where_clause='1 = 1'):
    sql = 'SELECT id, name, start_date, end_date FROM competition WHERE {where_clause}'.format(where_clause=where_clause)
    competitions = [Munch(r) for r in db().execute(sql)]
    for c in competitions:
        c.start_date = dtutil.ts2dt(c.start_date)
        c.end_date = dtutil.ts2dt(c.end_date)
    return competitions
