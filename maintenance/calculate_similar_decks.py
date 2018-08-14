import time
from typing import List

from decksite.data import archetype, deck
from magic.models import Deck
from shared import redis
from shared.database import sqlescape


def ad_hoc() -> None:
    archetypes = archetype.load_archetypes()
    for a in archetypes:
        print(f'Generating Similar Decks for {a.name} ({len(a.decks)} decks)')
        s = time.perf_counter()
        load_similar_decks(a.decks)
        t = time.perf_counter() - s
        print(f'Completed {len(a.decks)} decks in {t}')

def load_similar_decks(ds: List[Deck]) -> None:
    threshold = 20
    cards_escaped = ', '.join(sqlescape(name) for name in deck.all_card_names(ds))
    if not cards_escaped:
        for d in ds:
            d.similar_decks = []
        return
    potentially_similar = deck.load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card IN ({cards_escaped}))'.format(cards_escaped=cards_escaped))
    for d in ds:
        for psd in potentially_similar:
            psd.similarity_score = round(deck.similarity_score(d, psd) * 100)
        d.similar_decks = [psd for psd in potentially_similar if psd.similarity_score >= threshold and psd.id != d.id]
        d.similar_decks.sort(key=lambda d: -(d.similarity_score))
        redis.store('decksite:deck:{id}:similar'.format(id=d.id), d.similar_decks, ex=172800)
