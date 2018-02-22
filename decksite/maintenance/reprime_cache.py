from decksite.data import deck
from magic import multiverse, oracle


def run():
    multiverse.update_cache()
    oracle.init()
    ds = deck.load_decks()
    for d in ds:
        deck.prime_cache(d)
    return 'Done'
