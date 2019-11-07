from decksite.data import archetype, card, deck, person, rule
from magic import multiverse, oracle
from shared import redis


def run() -> None:
    multiverse.rebuild_cache()
    oracle.init()
    ds = deck.load_decks()
    for d in ds:
        redis.clear(f'decksite:deck:{d.id}')
        deck.prime_cache(d)
        redis.clear(f'decksite:deck:{d.id}')
    archetype.preaggregate()
    person.preaggregate()
    card.preaggregate()
    deck.preaggregate_omw()
    rule.cache_all_rules()
