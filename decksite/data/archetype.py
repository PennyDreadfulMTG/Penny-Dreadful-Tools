import sys
from typing import Dict, List

import titlecase
from anytree import NodeMixin

from decksite.data import deck
from decksite.database import db
from magic import rotation
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import DoesNotExistException, TooManyItemsException


class Archetype(Container, NodeMixin):
    pass

BASE_ARCHETYPES: Dict[Archetype, Archetype] = {}

def load_archetype(archetype):
    try:
        archetype_id = int(archetype)
    except ValueError:
        name = titlecase.titlecase(archetype.replace('-', ' '))
        archetype_id = db().value('SELECT id FROM archetype WHERE name = ?', [name])
        if not archetype_id:
            raise DoesNotExistException('Did not find archetype with name of `{name}`'.format(name=name))
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

def load_archetypes(where='1 = 1', merge=False):
    decks = deck.load_decks(where)
    archetypes = {}
    for d in decks:
        if d.archetype_id is None:
            continue
        key = 'merge' if merge else d.archetype_id
        archetype = archetypes.get(key, Archetype())
        archetype.id = d.archetype_id
        archetype.name = d.archetype_name
        archetype.decks = archetype.get('decks', []) + [d]
        archetype.all_wins = archetype.get('all_wins', 0) + (d.get('all_wins') or 0)
        archetype.all_losses = archetype.get('all_losses', 0) + (d.get('all_losses') or 0)
        archetype.all_draws = archetype.get('all_draws', 0) + (d.get('all_draws') or 0)
        if d.get('finish') == 1:
            archetype.all_tournament_wins = archetype.get('all_tournament_wins', 0) + 1
        if (d.get('finish') or sys.maxsize) <= 8:
            archetype.all_top8s = archetype.get('all_top8s', 0) + 1
            archetype.all_perfect_runs = archetype.get('all_perfect_runs', 0) + 1
        if d.created_date >= rotation.last_rotation():
            archetype.season_wins = archetype.get('season_wins', 0) + (d.get('season_wins') or 0)
            archetype.season_losses = archetype.get('season_losses', 0) + (d.get('season_losses') or 0)
            archetype.season_draws = archetype.get('season_draws', 0) + (d.get('season_draws') or 0)
            if d.get('finish') == 1:
                archetype.season_tournament_wins = archetype.get('season_tournament_wins', 0) + 1
            if (d.get('finish') or sys.maxsize) <= 8:
                archetype.season_top8s = archetype.get('season_top8s', 0) + 1
            if d.source_name == 'League' and d.wins >= 5 and d.losses == 0:
                archetype.season_perfect_runs = archetype.get('season_all_perfect_runs', 0) + 1
        archetypes[key] = archetype
    archetypes = list(archetypes.values())
    return archetypes

def load_archetypes_deckless(where='1 = 1', order_by='`season_num_decks` DESC, `all_num_decks` DESC, `season_wins` DESC, `all_wins` DESC'):
    sql = """
        SELECT
            a.id,
            a.name,
            aca.ancestor AS parent_id,
            {all_select},
            {season_select}
        FROM
            archetype AS a
        LEFT JOIN
            archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        LEFT JOIN
            archetype_closure AS acd ON a.id = acd.ancestor
        LEFT JOIN
            deck AS d ON acd.descendant = d.archetype_id
        {nwdl_join}
        WHERE
            {where}
        GROUP BY
            a.id,
            aca.ancestor -- aca.ancestor will be unique per a.id because of integrity constraints enforced elsewhere (each archetype has one ancestor) but we let the database know here.
        ORDER BY
            {order_by}
    """.format(all_select=deck.nwdl_all_select(), season_select=deck.nwdl_season_select(), nwdl_join=deck.nwdl_join(), where=where, order_by=order_by)
    archetypes = [Archetype(a) for a in db().execute(sql)]
    archetypes_by_id = {a.id: a for a in archetypes}
    for a in archetypes:
        a.decks = []
        a.parent = archetypes_by_id.get(a.parent_id, None)
    return archetypes

def load_archetypes_deckless_for(archetype_id) -> List[Archetype]:
    archetypes = load_archetypes_deckless()
    for a in archetypes:
        if int(a.id) == int(archetype_id):
            return list(a.ancestors) + [a] + list(a.descendants)
    return list()

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

def load_matchups(archetype_id):
    sql = """
        SELECT
            oa.id,
            oa.name,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS all_wins, -- IFNULL so we still count byes as wins.
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS all_losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS all_draws,
            IFNULL(ROUND((SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN dm.games <> IFNULL(odm.games, 0) THEN 1 ELSE 0 END), 0)) * 100, 1), '') AS all_win_percent,
            SUM(CASE WHEN d.created_date > %s AND dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS season_wins, -- IFNULL so we still count byes as wins.
            SUM(CASE WHEN d.created_date > %s AND dm.games < odm.games THEN 1 ELSE 0 END) AS season_losses,
            SUM(CASE WHEN d.created_date > %s AND dm.games = odm.games THEN 1 ELSE 0 END) AS season_draws,
            IFNULL(ROUND((SUM(CASE WHEN d.created_date > %s AND dm.games > odm.games THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN d.created_date > %s AND dm.games <> IFNULL(odm.games, 0) THEN 1 ELSE 0 END), 0)) * 100, 1), '') AS season_win_percent
        FROM
            archetype AS a
        INNER JOIN
            deck AS d ON d.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = a.id)
        INNER JOIN
            deck_match AS dm ON d.id = dm.deck_id
        INNER JOIN
            deck_match AS odm ON dm.match_id = odm.match_id AND odm.deck_id <> d.id
        INNER JOIN
            deck AS od ON od.id = odm.deck_id
        INNER JOIN
            archetype AS oa ON od.archetype_id IN (SELECT descendant FROM archetype_closure WHERE ancestor = oa.id)
        WHERE
            a.id = %s
        GROUP BY
            oa.id
        ORDER BY
            `season_wins` DESC, `all_wins` DESC
    """.format(all_select=deck.nwdl_all_select(), season_select=deck.nwdl_season_select(), nwdl_join=deck.nwdl_join())
    return [Container(m) for m in db().execute(sql, [int(rotation.last_rotation().timestamp())] * 5 + [archetype_id])]

def move(archetype_id, parent_id):
    db().begin()
    remove_sql = """
        DELETE a
        FROM archetype_closure AS a
        INNER JOIN archetype_closure AS d
            ON a.descendant = d.descendant
        LEFT JOIN archetype_closure AS x
            ON x.ancestor = d.ancestor AND x.descendant = a.ancestor
        WHERE d.ancestor = ? AND x.ancestor IS NULL
    """
    db().execute(remove_sql, [archetype_id])
    add_sql = """
        INSERT INTO archetype_closure (ancestor, descendant, depth)
            SELECT supertree.ancestor, subtree.descendant, supertree.depth + subtree.depth + 1
            FROM archetype_closure AS supertree JOIN archetype_closure AS subtree
            WHERE subtree.ancestor = ?
            AND supertree.descendant = ?
    """
    db().execute(add_sql, [archetype_id, parent_id])
    db().commit()

def base_archetypes():
    return [a for a in base_archetype_by_id().values() if a.parent is None]

def base_archetype_by_id():
    if len(BASE_ARCHETYPES) == 0:
        rebuild_archetypes()
    return BASE_ARCHETYPES

def rebuild_archetypes():
    archetypes_by_id = {a.id: a for a in load_archetypes_deckless()}
    for k, v in archetypes_by_id.items():
        p = v
        while p.parent is not None:
            p = p.parent
        BASE_ARCHETYPES[k] = p
