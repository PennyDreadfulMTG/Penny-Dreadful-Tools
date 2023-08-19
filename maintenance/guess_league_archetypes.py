from decksite.data import archetype, deck

HOURLY = True

def run() -> None:
    decks = deck.load_decks('NOT reviewed AND d.archetype_id IS NULL', order_by='d.created_date DESC', limit='LIMIT 100')
    deck.calculate_similar_decks(decks)
    for d in decks:
        for s in d.similar_decks:
            if s.reviewed and s.archetype_id is not None:
                sim = int(100 * deck.similarity_score(d, s))
                if d.archetype_id != s.archetype_id:
                    archetype.assign(d.id, s.archetype_id, None, False, sim)
                break
