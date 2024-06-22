import datetime
import sys

import github
from flask import url_for

from magic import fetcher, seasons
from magic.models import Deck
from shared import dtutil, logger, repo
from shared import redis_wrapper as redis
from shared.container import Container


def all_news(ds: list[Deck], start_date: datetime.datetime | None = None, end_date: datetime.datetime | None = None, max_items: int = sys.maxsize) -> list[Container]:
    if start_date is None:
        start_date = seasons.last_rotation()
    if end_date is None:
        end_date = dtutil.now()
    news: list[Container] = []
    news += tournament_winners(ds, max_items)
    news += perfect_league_runs(ds, max_items)
    news += code_merges(start_date, end_date, max_items, allow_fetch=False)
    news += subreddit(start_date, end_date, max_items, allow_fetch=False)
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


def tournament_winners(ds: list[Deck], max_items: int = sys.maxsize) -> list[Container]:
    winners = [d for d in ds if d.finish == 1][0:max_items]
    return [Container({'date': d.active_date, 'title': tournament_winner_headline(d), 'url': url_for('deck', deck_id=d.id), 'type': 'tournament-winner'}) for d in winners]


def tournament_winner_headline(d: Deck) -> str:
    return f'{d.person} won {d.competition_name} with {d.name}'


def perfect_league_runs(ds: list[Deck], max_items: int = sys.maxsize) -> list[Container]:
    perfect_runs = [d for d in ds if d.competition_type_name == 'League' and d.wins >= 5 and d.losses == 0][0:max_items]
    return [Container({'date': d.active_date, 'title': perfect_league_run_headline(d), 'url': url_for('deck', deck_id=d.id), 'type': 'perfect-league-run'}) for d in perfect_runs]


def perfect_league_run_headline(d: Deck) -> str:
    return f'{d.person} went 5–0 in {d.competition_name} with {d.name}'


def code_merges(start_date: datetime.datetime, end_date: datetime.datetime, max_items: int = sys.maxsize, force_refresh: bool = False, allow_fetch: bool = True) -> list[Container]:
    try:
        merges = []
        if not force_refresh:
            merges = redis.get_container_list('decksite:news:merges') or []
            for merge in merges:
                merge.date = dtutil.ts2dt(merge.date)
        if merges or not allow_fetch:
            return merges
        merges = [Container({'date': dtutil.UTC_TZ.localize(pull.merged_at), 'title': pull.title, 'url': pull.html_url, 'type': 'code-release'}) for pull in repo.get_pull_requests(start_date, end_date, max_items) if 'Not News' not in [label.name for label in pull.as_issue().labels]]
        redis.store('decksite:news:merges', merges, ex=7200)
        return merges
    except ConnectionError:
        logger.warning('ConnectionError talking to GitHub for merges')
        return []
    except github.BadCredentialsException:
        logger.warning('Bad GitHub credentials talking to GitHub for merges')
        return []


def subreddit(start_date: datetime.datetime, end_date: datetime.datetime, max_items: int = sys.maxsize, force_refresh: bool = False, allow_fetch: bool = True) -> list[Container]:
    try:
        redis_key = 'decksite:news:subreddit'
        items = []
        if not force_refresh:
            items = redis.get_container_list(redis_key) or []
            for item in items:
                item.date = dtutil.ts2dt(item.date)
        if items or not allow_fetch:
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
        redis.store(redis_key, items, ex=7200)
        return items
    except ConnectionError:
        logger.warning('ConnectionError talking to reddit')
        return []
