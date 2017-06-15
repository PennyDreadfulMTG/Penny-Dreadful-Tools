from munch import Munch

from magic import oracle, rotation
from shared.database import sqlescape

from decksite.data import deck, guarantee
from decksite.database import db

def load_archetype(archetype_id):
    return guarantee.exactly_one(load_archetypes('d.archetype_id = {archetype_id}'.format(archetype_id=sqlescape(archetype_id))))

def load_archetypes(where_clause='1 = 1'):
    decks = deck.load_decks(where_clause)
    archetypes = {}
    for d in decks:
        if d.archetype_id is None:
            continue
        archetype = archetypes.get(d.archetype_id, Munch())
        archetype.id = d.archetype_id
        archetype.name = d.archetype_name
        archetype.decks = archetype.get('decks', []) + [d]
        archetypes[archetype.id] = archetype
    return list(archetypes.values())
