from decksite.data import deck

def run():
    ds = deck.load_decks()
    for d in ds:
        deck.prime_cache(d)
    return 'Done'
