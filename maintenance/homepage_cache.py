from decksite.data import news
from magic import seasons
from shared import dtutil, logger

HOURLY = True

def run() -> None:
    start_date = seasons.last_rotation()
    end_date = dtutil.now()
    # Call these just to get the side effect of refreshing the redis cache.
    # The homepage is not allowed to fetch these because it is too slow, so we do it here not on user time.
    merges = news.code_merges(start_date, end_date, force_refresh=True)
    logger.info(f'Found {len(merges)} merges in homepage cache run')
    posts = news.subreddit(start_date, end_date, force_refresh=True)
    logger.info(f'Found {len(posts)} reddit posts in homepage cache run')
