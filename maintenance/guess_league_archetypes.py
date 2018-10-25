from decksite.data import archetype, deck

HOURLY = True

def run() -> None:
    decks = deck.load_decks('archetype_id is null')
    deck.calculate_similar_decks(decks)
    for d in decks:
        if d.similar_decks:
            archetype.assign(d.id, d.similar_decks[0].archetype_id, False)
