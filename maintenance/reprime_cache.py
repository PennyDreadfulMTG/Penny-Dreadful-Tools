from decksite.data import archetype, card, deck, person, season
from magic import multiverse, oracle
from shared import redis_wrapper as redis


def run() -> None:
    multiverse.rebuild_cache()
    oracle.init()
    archetype.preaggregate()
    person.preaggregate()
    card.preaggregate()
    deck.preaggregate()
    season.preaggregate()
    # rule.cache_all_rules()
