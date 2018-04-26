import datetime
import sys
from typing import List

from decksite.database import db
from shared import dtutil
from shared.container import Container


def load_news(start_date: int = 0, end_date: int = sys.maxsize, max_items: int = sys.maxsize) -> List[Container]:
    sql = """
        SELECT
            id,
            `date`,
            title,
            url
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

def add_or_update_news(news_item_id: int, date: datetime.datetime, title: str, url: str) -> None:
    ts = dtutil.dt2ts(date)
    if news_item_id is not None:
        update_news(news_item_id, ts, title, url)
        return
    add_news(ts, title, url)

def update_news(news_item_id: int, ts: int, title: str, url: str) -> None:
    sql = 'UPDATE news_item SET `date` = %s, title = %s, url = %s WHERE id = %s'
    db().execute(sql, [ts, title, url, news_item_id])

def add_news(ts: int, title: str, url: str) -> None:
    sql = 'INSERT INTO news_item (`date`, title, url) VALUES (%s, %s, %s)'
    db().execute(sql, [ts, title, url])

def delete(news_item_id: int) -> None:
    sql = 'DELETE FROM news_item WHERE id = %s'
    db().execute(sql, [news_item_id])
