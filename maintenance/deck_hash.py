import hashlib

from decksite.data import deck
from decksite.database import db
from shared import redis_wrapper as redis

DAILY = True

def run() -> None:
    recalculate()

def recalculate(deck_ids: set[int] | None = None) -> None:
    if deck_ids is not None and not deck_ids:
        return
    if deck_ids is None:
        where = 'TRUE'
    else:
        where = 'd.id IN ({})'.format(', '.join(map(str, sorted(deck_ids))))
        redis.clear(*(f'decksite:deck:{deck_id}' for deck_id in deck_ids))
    all_decks = deck.load_decks(where=where)
    for d in all_decks:
        # Recalculate all hashes, in case they've changed.  Or we've changed the default sort order.
        cards = {'maindeck': d['maindeck'], 'sideboard': d['sideboard']}
        deckhash = hashlib.sha1(repr(cards).encode('utf-8')).hexdigest()
        if d['decklist_hash'] != deckhash:
            print(f"{d.id}: hash was {d['decklist_hash']} now {deckhash}")
            db().execute('UPDATE deck SET decklist_hash = %s WHERE id = %s', [deckhash, d['id']])
            redis.clear(f'decksite:deck:{d.id}')
