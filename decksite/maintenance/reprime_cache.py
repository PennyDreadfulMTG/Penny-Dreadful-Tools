from magic import multiverse, oracle

from decksite.data import deck

def ad_hoc():
    multiverse.update_cache()
    oracle.init()
    ds = deck.load_decks()
    for d in ds:
        deck.prime_cache(d)
    return 'Done'
