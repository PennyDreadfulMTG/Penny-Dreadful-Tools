from decksite import league
from magic import multiverse
from shared import redis

from . import insert_seasons, reprime_cache


def ad_hoc() -> None:
    league.set_status(league.Status.CLOSED)
    multiverse.init() # New Cards?
    multiverse.set_legal_cards() # PD current list
    multiverse.update_pd_legality() # PD previous lists
    reprime_cache.run() # Update deck legalities
    insert_seasons.run() # Make sure Season table is up to date
    if redis.REDIS: # Clear the redis cache
        redis.REDIS.flushdb() # type: ignore[no-untyped-call]
    league.set_status(league.Status.OPEN)
