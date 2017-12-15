from magic import multiverse

from decksite.data import deck

def ad_hoc():
    multiverse.update_cache()
    ds = deck.load_decks()
    for d in ds:
        deck.prime_cache(d)
    return 'Done'
