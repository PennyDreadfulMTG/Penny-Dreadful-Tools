from decksite.data import deck
from magic import multiverse, oracle
from shared import redis


def run():
    multiverse.update_cache()
    oracle.init()
    ds = deck.load_decks()
    for d in ds:
        redis.clear(f'decksite:deck:{d.id}')
        deck.prime_cache(d)
    return 'Done'
