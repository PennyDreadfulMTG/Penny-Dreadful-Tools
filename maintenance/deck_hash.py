import hashlib

from decksite.data import deck
from decksite.database import db
from shared import redis


def run() -> None:
    all_decks = deck.load_decks()
    for d in all_decks:
        # Recalculate all hashes, in case they've changed.  Or we've changed the default sort order.
        cards = {'maindeck': d['maindeck'], 'sideboard': d['sideboard']}
        deckhash = hashlib.sha1(repr(cards).encode('utf-8')).hexdigest()
        if d['decklist_hash'] != deckhash:
            print(f"{d.id}: hash was {d['decklist_hash']} now {deckhash}")
            db().execute('UPDATE deck SET decklist_hash = %s WHERE id = %s', [deckhash, d['id']])
            redis.clear(f'decksite:deck:{d.id}')
