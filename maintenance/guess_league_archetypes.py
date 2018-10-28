from decksite.data import archetype, deck

HOURLY = True

def run() -> None:
    decks = deck.load_decks('archetype_id is null')
    deck.calculate_similar_decks(decks)
    for d in decks:
        for s in d.similar_decks:
            if s.archetype_id is not None:
                sim = int(100 * deck.similarity_score(d, s))
                archetype.assign(d.id, s.archetype_id, False, sim)
                break
