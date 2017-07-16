from anytree import NodeMixin

from magic import rotation
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import TooManyItemsException

from decksite.data import deck
from decksite.database import db

def load_archetype(archetype_id):
    archetypes = load_archetypes('d.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = {archetype_id})'.format(archetype_id=sqlescape(archetype_id)), True)
    if len(archetypes) > 1:
        raise TooManyItemsException('Found {n} archetypes when expecting 1 at most'.format(n=len(archetypes)))
    archetype = archetypes[0] if len(archetypes) == 1 else Archetype()
    # Because load_archetypes loads the root archetype and all below merged the id and name might not be those of the root archetype. Overwrite.
    archetype.id = int(archetype_id)
    archetype.name = db().value('SELECT name FROM archetype WHERE id = ?', [archetype_id])
    if len(archetypes) == 0:
        archetype.decks = []
    return archetype

def load_archetypes(where_clause='1 = 1', merge=False):
    decks = deck.load_decks(where_clause)
    archetypes = {}
    for d in decks:
        if d.archetype_id is None:
            continue
        key = 'merge' if merge else d.archetype_id
        archetype = archetypes.get(key, Archetype())
        archetype.id = d.archetype_id
        archetype.name = d.archetype_name
        archetype.decks = archetype.get('decks', []) + [d]
        archetype.all = archetype.get('all', Archetype())
        archetype.season = archetype.all.get('season', Archetype())
        archetype.all.wins = archetype.all.get('wins', 0) + (d.get('wins') or 0)
        archetype.all.losses = archetype.all.get('losses', 0) + (d.get('losses') or 0)
        archetype.all.draws = archetype.all.get('draws', 0) + (d.get('draws') or 0)
        if d.created_date >= rotation.last_rotation():
            archetype.season.wins = archetype.season.get('wins', 0) + (d.get('wins') or 0)
            archetype.season.losses = archetype.season.get('losses', 0) + (d.get('losses') or 0)
            archetype.season.draws = archetype.season.get('draws', 0) + (d.get('draws') or 0)
        archetypes[key] = archetype
    archetypes = list(archetypes.values())
    return archetypes

def load_archetypes_deckless(where='1 = 1', order_by='`season.num_decks` DESC, `all.num_decks` DESC, `season.wins` DESC, `all.wins` DESC'):
    sql = """
        SELECT
            a.id,
            a.name,
            aca.ancestor AS parent_id,

            COUNT(DISTINCT d.id) AS `all.num_decks`,
            SUM(d.wins) AS `all.wins`,
            SUM(d.losses) AS `all.losses`,
            SUM(d.draws) AS `all.draws`,
            IFNULL(ROUND((SUM(wins) / SUM(wins + losses)) * 100, 1), '') AS `all.win_percent`,

            SUM(CASE WHEN d.created_date >= %s THEN 1 ELSE 0 END) AS `season.num_decks`,
            SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) AS `season.wins`,
            SUM(CASE WHEN d.created_date >= %s THEN losses ELSE 0 END) AS `season.losses`,
            SUM(CASE WHEN d.created_date >= %s THEN draws ELSE 0 END) AS `season.draws`,
            IFNULL(ROUND((SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END + CASE WHEN d.created_date >= %s THEN losses ELSE 0 END)) * 100, 1), '') AS `season.win_percent`

        FROM archetype AS a
        LEFT JOIN archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        LEFT JOIN archetype_closure AS acd ON a.id = acd.ancestor
        LEFT JOIN deck AS d ON acd.descendant = d.archetype_id
        WHERE {where}
        GROUP BY a.id
        ORDER BY {order_by}
    """.format(where=where, order_by=order_by)
    archetypes = [Archetype(a) for a in db().execute(sql, [rotation.last_rotation().timestamp()] * 7)]
    archetypes_by_id = {a.id: a for a in archetypes}
    for a in archetypes:
        a.decks = []
        a.parent = archetypes_by_id.get(a.parent_id, None)
    return archetypes

def load_archetypes_deckless_for(archetype_id):
    archetypes = load_archetypes_deckless()
    for a in archetypes:
        if int(a.id) == int(archetype_id):
            return list(a.ancestors) + [a] + list(a.descendants)

def add(name, parent):
    archetype_id = db().insert('INSERT INTO archetype (name) VALUES (?)', [name])
    ancestors = db().execute('SELECT ancestor, depth FROM archetype_closure WHERE descendant = ?', [sqlescape(parent)])
    sql = 'INSERT INTO archetype_closure (ancestor, descendant, depth) VALUES '
    for a in ancestors:
        sql += '({ancestor}, {descendant}, {depth}), '.format(ancestor=sqlescape(a['ancestor']), descendant=archetype_id, depth=int(a['depth']) + 1)
    sql += '({ancestor}, {descendant}, {depth})'.format(ancestor=archetype_id, descendant=archetype_id, depth=0)
    return db().execute(sql)

def assign(deck_id, archetype_id):
    return db().execute('UPDATE deck SET reviewed = TRUE, archetype_id = ? WHERE id = ?', [archetype_id, deck_id])

class Archetype(Container, NodeMixin):
    pass
