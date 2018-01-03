import sys

from shared import dtutil
from shared.container import Container

from decksite.database import db

def load_news(start_date=0, end_date=sys.maxsize, max_items=sys.maxsize):
    sql = """
        SELECT
            id,
            `date`,
            title,
            body
        FROM
            news_item
        WHERE
            `date` >= %s
        AND
            `date` <= %s
        ORDER BY
            `date` DESC
        LIMIT
            %s
    """
    results = [Container(r) for r in db().execute(sql, [start_date, end_date, max_items])]
    for result in results:
        result.date = dtutil.ts2dt(result.date)
        result.form_date = dtutil.form_date(result.date, dtutil.WOTC_TZ)
        result.display_date = dtutil.display_date(result.date)
    return results

def add_or_update_news(id, date, title, body):
    date = dtutil.dt2ts(date)
    if id is not None:
        return update_news(id, date, title, body)
    return add_news(date, title, body)

def update_news(id, date, title, body):
    sql = 'UPDATE news_item SET `date` = %s, title = %s, body = %s WHERE id = %s'
    print([date, title, body, id])
    return db().execute(sql, [date, title, body, id])

def add_news(date, title, body):
    sql = 'INSERT INTO news_item (`date`, title, body) VALUES (%s, %s, %s)'
    print([date, title, body])
    return db().execute(sql, [date, title, body])

def delete(id):
    sql = 'DELETE FROM news_item WHERE id = %s'
    return db().execute(sql, [id])
