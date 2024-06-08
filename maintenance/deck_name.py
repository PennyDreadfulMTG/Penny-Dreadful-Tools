from decksite import deck_name
from decksite.data import deck

# We have pretty good tests for deck_name sanitization, but sometimes you want to see what a change in the algorithm would do to real deck names.
# Make your changes in deck_name.py and then run this to see which decks would change if re-normalized.

def ad_hoc() -> None:
    ds, _ = deck.load_decks()
    for d in ds:
        current = d.name
        potential = deck_name.normalize(d)
        if current != potential:
            print(f'{potential} <- {current} ({d.original_name})')
