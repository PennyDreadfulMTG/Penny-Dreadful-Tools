import datetime
import sys
from typing import List

from flask import url_for

from decksite.data import deck
from decksite.database import db
from magic import fetcher
from magic.models import Deck
from shared import dtutil, redis_wrapper as redis, repo
from shared.container import Container
from shared.database import sqlescape


def all_news(start_date: datetime.datetime = None, end_date: datetime.datetime = None, max_items: int = sys.maxsize) -> List[Container]:
    if start_date is None:
        start_date = dtutil.ts2dt(0)
    if end_date is None:
        end_date = dtutil.now()
    news: List[Container] = []
    news += load_news(start_date, end_date, max_items)
    news += tournament_winners(start_date, end_date, max_items)
    news += perfect_league_runs(start_date, end_date, max_items)
    news += code_merges(start_date, end_date, max_items)
    news += subreddit(start_date, end_date, max_items)
    news = sorted(news, key=lambda item: item.date, reverse=True)
    results = []
    for item in news:
        if item.date > end_date:
            continue
        if item.date < start_date:
            break
        item.display_date = dtutil.display_date(item.date)
        results.append(item)
        if len(results) >= max_items:
            break
    return results

def load_news(start_date: datetime.datetime = None, end_date: datetime.datetime = None, max_items: int = sys.maxsize) -> List[Container]:
    if start_date is None:
        start_date = dtutil.ts2dt(0)
    if end_date is None:
        end_date = dtutil.now()
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
    results = [Container(r) for r in db().select(sql, [dtutil.dt2ts(start_date), dtutil.dt2ts(end_date), max_items])]
    for result in results:
        result.date = dtutil.ts2dt(result.date)
        result.form_date = dtutil.form_date(result.date, dtutil.WOTC_TZ)
        result.display_date = dtutil.display_date(result.date)
        result.type = 'site-news'
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

def tournament_winners(start_date: datetime.datetime, end_date: datetime.datetime, max_items: int = sys.maxsize) -> List[Container]:
    where = 'd.finish = 1 AND d.created_date > {start_date} AND d.created_date <= {end_date}'.format(start_date=sqlescape(dtutil.dt2ts(start_date)), end_date=sqlescape(dtutil.dt2ts(end_date)))
    ds = deck.load_decks(where, limit=f'LIMIT {max_items}')
    return [Container({'date': d.active_date, 'title': tournament_winner_headline(d), 'url': url_for('deck', deck_id=d.id), 'type': 'tournament-winner'}) for d in ds]

def tournament_winner_headline(d: Deck) -> str:
    return f'{d.person} won {d.competition_name} with {d.name}'

def perfect_league_runs(start_date: datetime.datetime, end_date: datetime.datetime, max_items: int = sys.maxsize) -> List[Container]:
    where = "ct.name = 'League' AND d.created_date > {start_date} AND d.created_date <= {end_date}".format(start_date=sqlescape(dtutil.dt2ts(start_date)), end_date=sqlescape(dtutil.dt2ts(end_date)))
    having = 'wins >= 5 AND losses = 0'
    ds = deck.load_decks(where, having=having, limit=f'LIMIT {max_items}')
    return [Container({'date': d.active_date, 'title': perfect_league_run_headline(d), 'url': url_for('deck', deck_id=d.id), 'type': 'perfect-league-run'}) for d in ds]

def perfect_league_run_headline(d: Deck) -> str:
    return f'{d.person} went 5–0 in {d.competition_name} with {d.name}'

def code_merges(start_date: datetime.datetime, end_date: datetime.datetime, max_items: int = sys.maxsize) -> List[Container]:
    try:
        merges = redis.get_container_list('decksite:news:merges')
        if merges is None:
            merges = [Container({'date': dtutil.UTC_TZ.localize(pull.merged_at), 'title': pull.title, 'url': pull.html_url, 'type': 'code-release'}) for pull in repo.get_pull_requests(start_date, end_date, max_items) if not 'Not News' in [l.name for l in pull.as_issue().labels]]
            redis.store('decksite:news:merges', merges, ex=3600)
        else:
            for merge in merges:
                merge.date = dtutil.ts2dt(merge.date)
        return merges
    except ConnectionError:
        return []

def subreddit(start_date: datetime.datetime, end_date: datetime.datetime, max_items: int = sys.maxsize) -> List[Container]:
    try:
        redis_key = 'decksite:news:subreddit'
        items = redis.get_container_list(redis_key)
        if items:
            for item in items:
                item.date = dtutil.ts2dt(item.date)
            return items
        feed = fetcher.subreddit()
        items = []
        for entry in feed.entries:
            item = Container({'title': entry.title, 'date': dtutil.parse(entry.updated, '%Y-%m-%dT%H:%M:%S+00:00', dtutil.UTC_TZ), 'url': entry.link, 'type': 'subreddit-post'})
            if item.date > end_date:
                continue
            if item.date < start_date:
                break
            items.append(item)
            if len(items) >= max_items:
                break
        redis.store(redis_key, items, ex=3600)
        return items
    except ConnectionError:
        return []
