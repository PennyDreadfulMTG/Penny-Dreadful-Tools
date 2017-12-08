from magic import multiverse

from decksite.data import deck

def run():
    multiverse.init()
    multiverse.update_cache()
    ds = deck.load_decks()
    for d in ds:
        deck.prime_cache(d)
    return 'Done'
