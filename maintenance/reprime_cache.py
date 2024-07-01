import time
from collections.abc import Callable

from decksite.data import archetype, card, deck, person, playability, season
from magic import multiverse, oracle

DAILY = True


def call_timed(func: Callable) -> None:
    timer = time.perf_counter()
    func()
    t = time.perf_counter() - timer
    print(f'{func.__module__}.{func.__name__} completed in {t}')


def run() -> None:
    call_timed(multiverse.rebuild_cache)
    oracle.init()
    call_timed(archetype.preaggregate)
    call_timed(person.preaggregate)
    call_timed(card.preaggregate)
    call_timed(deck.preaggregate)
    call_timed(season.preaggregate)
    call_timed(playability.preaggregate)
    # call_timed(rule.cache_all_rules)
