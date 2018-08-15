import time

from decksite.data import archetype, deck


def ad_hoc() -> None:
    archetypes = archetype.load_archetypes()
    for a in archetypes:
        print(f'Generating Similar Decks for {a.name} ({len(a.decks)} decks)')
        s = time.perf_counter()
        deck.calculate_similar_decks(a.decks)
        t = time.perf_counter() - s
        print(f'Completed {len(a.decks)} decks in {t}')
