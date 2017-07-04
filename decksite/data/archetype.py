from munch import Munch

from shared.database import sqlescape
from shared.pd_exception import TooManyItemsException

from decksite.data import deck
from decksite.database import db

def load_archetype(archetype_id):
    archetypes = load_archetypes('d.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = {archetype_id})'.format(archetype_id=sqlescape(archetype_id)), True)
    if len(archetypes) > 1:
        raise TooManyItemsException('Found {n} archetypes when expecting 1 at most'.format(n=len(archetypes)))
    archetype = archetypes[0] if len(archetypes) == 1 else Munch()
    # Because load_archetypes loads the root archetype and all below merged the id and name might not be those of the root archetype. Overwrite.
    archetype.id = int(archetype_id)
    archetype.name = db().value('SELECT name FROM archetype WHERE id = ?', [archetype_id])
    if len(archetypes) == 0:
        archetype.decks = []
        archetype.tree = load_tree(archetype)
    return archetype

def load_archetypes(where_clause='1 = 1', merge=False):
    decks = deck.load_decks(where_clause)
    archetypes = {}
    for d in decks:
        if d.archetype_id is None:
            continue
        key = 'merge' if merge else d.archetype_id
        archetype = archetypes.get(key, Munch())
        archetype.id = d.archetype_id
        archetype.name = d.archetype_name
        archetype.decks = archetype.get('decks', []) + [d]
        archetype.wins = archetype.get('wins', 0) or 0 + d.get('wins', 0)
        archetype.losses = archetype.get('losses', 0) or 0 + d.get('losses', 0)
        archetype.draws = archetype.get('draws', 0) or 0 + d.get('draws', 0)
        archetypes[key] = archetype
    archetypes = list(archetypes.values())
    for a in archetypes:
        a.tree = load_tree(a)
    return archetypes

def load_archetypes_without_decks():
    archetypes = [Munch(a) for a in db().execute('SELECT id, name FROM archetype')]
    for a in archetypes:
        a.decks = []
        a.tree = load_tree(a)
    return archetypes

def load_tree(archetype):
    sql = """
        SELECT a.id, a.name, -ac.depth AS pos, p.ancestor AS parent
        FROM archetype AS a
        LEFT JOIN archetype_closure AS ac ON a.id = ac.ancestor
        LEFT JOIN archetype_closure AS p ON a.id = p.descendant AND p.depth = 1
        WHERE ac.descendant = ?
        UNION
        SELECT a.id, a.name, ac.depth AS pos, p.ancestor AS parent
        FROM archetype AS a
        LEFT JOIN archetype_closure AS ac ON a.id = ac.descendant
        LEFT JOIN archetype_closure AS p ON a.id = p.descendant AND p.depth = 1
        WHERE ac.ancestor = ?
        ORDER BY pos
        """
    rs = db().execute(sql, [archetype.id] * 2)
    nodes = {}
    for row in rs:
        nodes[row['id']] = row
    for row in rs:
        if row.get('parent') is not None:
            nodes[row['parent']]['children'] = nodes[row['parent']].get('children', []) + [row]
        else:
            root = nodes[row['id']]
    archetype.is_root = nodes[archetype.id].get('parent') is None
    return root

def add(name, parent):
    archetype_id = db().insert('INSERT INTO archetype (name) VALUES (?)', [name])
    ancestors = db().execute('SELECT ancestor, depth FROM archetype_closure WHERE descendant = ?', [sqlescape(parent)])
    sql = 'INSERT INTO archetype_closure (ancestor, descendant, depth) VALUES '
    for a in ancestors:
        sql += '({ancestor}, {descendant}, {depth}), '.format(ancestor=sqlescape(a['ancestor']), descendant=archetype_id, depth=int(a['depth']) + 1)
    sql += '({ancestor}, {descendant}, {depth})'.format(ancestor=archetype_id, descendant=archetype_id, depth=0)
    return db().execute(sql)

def assign(deck_id, archetype_id):
    return db().execute('UPDATE deck SET archetype_id = ? WHERE id = ?', [archetype_id, deck_id])
