from decksite.data import archetype, deck

HOURLY = True

def run() -> None:
    archetype.clear_old_predictions()
    decks = deck.load_decks('archetype_id is null')
    deck.calculate_similar_decks(decks)
    for d in decks:
        if d.similar_decks and d.similar_decks[0].archetype_id is not None:
            conf = int(100 * deck.similarity_score(d, d.similar_decks[0]))
            archetype.assign(d.id, d.similar_decks[0].archetype_id, False, conf)
