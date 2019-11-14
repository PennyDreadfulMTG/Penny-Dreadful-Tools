import sys
from typing import Dict, List, Optional, Union

import titlecase
from anytree import NodeMixin
from anytree.iterators import PreOrderIter

from decksite.data import deck, preaggregation, query
from decksite.database import db
from shared import guarantee
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import retry_after_calling
from shared.pd_exception import DoesNotExistException


class Archetype(Container, NodeMixin):
    pass

BASE_ARCHETYPES: Dict[Archetype, Archetype] = {}

# pylint: disable=attribute-defined-outside-init
def load_archetype(archetype: Union[int, str], season_id: int = None) -> Archetype:
    try:
        archetype_id = int(archetype)
    except ValueError:
        name = titlecase.titlecase(archetype)
        name_without_dashes = name.replace('-', ' ')
        archetype_id = db().value("SELECT id FROM archetype WHERE REPLACE(name, '-', ' ') = %s", [name_without_dashes])
        if not archetype_id:
            raise DoesNotExistException('Did not find archetype with name of `{name}`'.format(name=name))
    archetypes = load_archetypes(where=query.archetype_where(archetype_id), merge=True, season_id=season_id)
    arch = guarantee.exactly_one(archetypes, 'archetypes') if archetypes else Archetype()
    # Because load_archetypes loads the root archetype and all below merged the id and name might not be those of the root archetype. Overwrite.
    arch.id = int(archetype_id)
    arch.name = db().value('SELECT name FROM archetype WHERE id = %s', [archetype_id])
    if len(archetypes) == 0:
        arch.decks = []
    arch.decks_tournament = arch.get('decks_tournament', [])
    return arch

def load_archetypes(where: str = 'TRUE', merge: bool = False, season_id: int = None) -> List[Archetype]:
    decks = deck.load_decks(where, season_id=season_id)
    archetypes: Dict[str, Archetype] = {}
    for d in decks:
        if d.archetype_id is None:
            continue
        key = 'merge' if merge else d.archetype_id
        archetype = archetypes.get(key, Archetype())
        archetype.id = d.archetype_id
        archetype.name = d.archetype_name

        archetype.decks = archetype.get('decks', []) + [d]
        archetype.wins = archetype.get('wins', 0) + (d.get('wins') or 0)
        archetype.losses = archetype.get('losses', 0) + (d.get('losses') or 0)
        archetype.draws = archetype.get('draws', 0) + (d.get('draws') or 0)

        archetype.decks_tournament = archetype.get('decks_tournament', [])
        archetype.wins_tournament = archetype.get('wins_tournament', 0)
        archetype.losses_tournament = archetype.get('losses_tournament', 0)
        archetype.draws_tournament = archetype.get('draws_tournament', 0)
        if d.competition_type_name == 'Gatherling':
            archetype.decks_tournament.append(d)
            archetype.wins_tournament += (d.get('wins') or 0)
            archetype.losses_tournament += (d.get('losses') or 0)
            archetype.draws_tournament += (d.get('draws') or 0)

        if d.get('finish') == 1:
            archetype.tournament_wins = archetype.get('tournament_wins', 0) + 1
        if (d.get('finish') or sys.maxsize) <= 8:
            archetype.top8s = archetype.get('top8s', 0) + 1
            archetype.perfect_runs = archetype.get('perfect_runs', 0) + 1
        archetypes[key] = archetype
    archetype_list = list(archetypes.values())
    return archetype_list

def load_archetypes_deckless_for(archetype_id: int, season_id: int = None) -> List[Archetype]:
    archetypes = load_archetypes_deckless(season_id=season_id)
    for a in archetypes:
        if int(a.id) == int(archetype_id):
            return list(a.ancestors) + [a] + list(a.descendants)
    return list()

def add(name: str, parent: int) -> None:
    archetype_id = db().insert('INSERT INTO archetype (name) VALUES (%s)', [name])
    ancestors = db().select('SELECT ancestor, depth FROM archetype_closure WHERE descendant = %s', [parent])
    sql = 'INSERT INTO archetype_closure (ancestor, descendant, depth) VALUES '
    for a in ancestors:
        sql += '({ancestor}, {descendant}, {depth}), '.format(ancestor=sqlescape(a['ancestor']), descendant=archetype_id, depth=int(a['depth']) + 1)
    sql += '({ancestor}, {descendant}, {depth})'.format(ancestor=archetype_id, descendant=archetype_id, depth=0)
    db().execute(sql)

def assign(deck_id: int, archetype_id: int, reviewed: bool = True, similarity: Optional[int] = None) -> None:
    and_clause = '' if reviewed else 'AND reviewed is FALSE'
    db().execute(f'UPDATE deck SET reviewed = %s, archetype_id = %s WHERE id = %s {and_clause}', [reviewed, archetype_id, deck_id])
    if not reviewed and similarity is not None:
        db().execute(f'UPDATE deck_cache SET similarity = %s WHERE deck_id = %s', [similarity, deck_id])

def move(archetype_id: int, parent_id: int) -> None:
    db().begin('move_archetype')
    remove_sql = """
        DELETE a
        FROM archetype_closure AS a
        INNER JOIN archetype_closure AS d
            ON a.descendant = d.descendant
        LEFT JOIN archetype_closure AS x
            ON x.ancestor = d.ancestor AND x.descendant = a.ancestor
        WHERE d.ancestor = %s AND x.ancestor IS NULL
    """
    db().execute(remove_sql, [archetype_id])
    add_sql = """
        INSERT INTO archetype_closure (ancestor, descendant, depth)
            SELECT supertree.ancestor, subtree.descendant, supertree.depth + subtree.depth + 1
            FROM archetype_closure AS supertree JOIN archetype_closure AS subtree
            WHERE subtree.ancestor = %s
            AND supertree.descendant = %s
    """
    db().execute(add_sql, [archetype_id, parent_id])
    db().commit('move_archetype')

def rename(archetype_id: int, new_name: str) -> None:
    db().execute('UPDATE archetype SET name = %s WHERE id = %s', [new_name, archetype_id])

def update_description(archetype_id: int, description: str) -> None:
    db().execute('UPDATE archetype SET description = %s WHERE id = %s', [description, archetype_id])

def base_archetypes() -> List[Archetype]:
    return [a for a in base_archetype_by_id().values() if a.parent is None]

def base_archetype_by_id() -> Dict[Archetype, Archetype]:
    if len(BASE_ARCHETYPES) == 0:
        rebuild_archetypes()
    return BASE_ARCHETYPES

def rebuild_archetypes() -> None:
    archetypes_by_id = {a.id: a for a in load_archetypes_deckless()}
    for k, v in archetypes_by_id.items():
        p = v
        while p.parent is not None:
            p = p.parent
        BASE_ARCHETYPES[k] = p

def preaggregate() -> None:
    preaggregate_archetypes()
    preaggregate_archetype_person()
    preaggregate_matchups()
    preaggregate_matchups_person()

def preaggregate_archetypes() -> None:
    table = '_archetype_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            archetype_id INT NOT NULL,
            season_id INT NOT NULL,
            num_decks INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            num_decks_tournament INT NOT NULL,
            wins_tournament INT NOT NULL,
            losses_tournament INT NOT NULL,
            draws_tournament INT NOT NULL,
            PRIMARY KEY (season_id, archetype_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            season.id AS season_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(wins), 0) AS wins,
            IFNULL(SUM(losses), 0) AS losses,
            IFNULL(SUM(draws), 0) AS draws,
            SUM(CASE WHEN wins >= 5 AND losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            SUM(CASE WHEN (d.id IS NOT NULL) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS num_decks_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN wins ELSE 0 END), 0) AS wins_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN losses ELSE 0 END), 0) AS losses_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN draws ELSE 0 END), 0) AS draws_tournament
        FROM
            archetype AS a
        LEFT JOIN
            archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        LEFT JOIN
            archetype_closure AS acd ON a.id = acd.ancestor
        LEFT JOIN
            deck AS d ON acd.descendant = d.archetype_id
        {competition_join}
        {season_join}
        {nwdl_join}
        GROUP BY
            a.id,
            aca.ancestor, -- aca.ancestor will be unique per a.id because of integrity constraints enforced elsewhere (each archetype has one ancestor) but we let the database know here.
            season.id
        HAVING
            season.id IS NOT NULL
    """.format(table=table,
               competition_join=query.competition_join(),
               season_join=query.season_join(),
               nwdl_join=deck.nwdl_join())
    preaggregation.preaggregate(table, sql)

def preaggregate_archetype_person() -> None:
    # This preaggregation fails if I use the obvious name _new_archetype_person_stats but works with any other name. It's confusing.
    table = '_arch_person_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            archetype_id INT NOT NULL,
            person_id INT NOT NULL,
            season_id INT NOT NULL,
            num_decks INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            num_decks_tournament INT NOT NULL,
            wins_tournament INT NOT NULL,
            losses_tournament INT NOT NULL,
            draws_tournament INT NOT NULL,
            PRIMARY KEY (person_id, season_id, archetype_id),
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            d.person_id,
            season.id AS season_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(wins), 0) AS wins,
            IFNULL(SUM(losses), 0) AS losses,
            IFNULL(SUM(draws), 0) AS draws,
            SUM(CASE WHEN wins >= 5 AND losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            SUM(CASE WHEN (d.id IS NOT NULL) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS num_decks_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN wins ELSE 0 END), 0) AS wins_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN losses ELSE 0 END), 0) AS losses_tournament,
            IFNULL(SUM(CASE WHEN ct.name = 'Gatherling' THEN draws ELSE 0 END), 0) AS draws_tournament
        FROM
            archetype AS a
        LEFT JOIN
            archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        LEFT JOIN
            archetype_closure AS acd ON a.id = acd.ancestor
        LEFT JOIN
            deck AS d ON acd.descendant = d.archetype_id
        {competition_join}
        {season_join}
        {nwdl_join}
        GROUP BY
            a.id,
            d.person_id,
            season.id
        HAVING
            season.id IS NOT NULL
    """.format(table=table,
               competition_join=query.competition_join(),
               season_join=query.season_join(),
               nwdl_join=deck.nwdl_join())
    preaggregation.preaggregate(table, sql)

def preaggregate_matchups() -> None:
    table = '_matchup_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            archetype_id INT NOT NULL,
            opponent_archetype_id INT NOT NULL,
            season_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            wins_tournament INT NOT NULL,
            losses_tournament INT NOT NULL,
            draws_tournament INT NOT NULL,
            PRIMARY KEY (season_id, archetype_id, opponent_archetype_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (opponent_archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            oa.id AS opponent_archetype_id,
            season.id AS season_id,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins, -- IFNULL so we still count byes as wins.
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws,
            SUM(CASE WHEN (dm.games > IFNULL(odm.games, 0)) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS wins_tournament,
            SUM(CASE WHEN (dm.games < IFNULL(odm.games, 0)) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS losses_tournament,
            SUM(CASE WHEN (dm.games = IFNULL(odm.games, 0)) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS draws_tournament
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
        {competition_join}
        {season_join}
        GROUP BY
            a.id,
            oa.id,
            season.id
    """.format(table=table, competition_join=query.competition_join(), season_join=query.season_join())
    preaggregation.preaggregate(table, sql)

def preaggregate_matchups_person() -> None:
    # Obvious name `_matchup_person_stats` fails with (1005, 'Can\'t create table `decksite`.`_new_matchup_person_stats` (errno: 121 "Duplicate key on write or update")'). Odd.
    table = '_matchup_ps_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
            archetype_id INT NOT NULL,
            opponent_archetype_id INT NOT NULL,
            person_id INT NOT NULL,
            season_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            wins_tournament INT NOT NULL,
            losses_tournament INT NOT NULL,
            draws_tournament INT NOT NULL,
            PRIMARY KEY (season_id, archetype_id, opponent_archetype_id, person_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (opponent_archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            oa.id AS opponent_archetype_id,
            d.person_id,
            season.id AS season_id,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins, -- IFNULL so we still count byes as wins.
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws,
            SUM(CASE WHEN (dm.games > IFNULL(odm.games, 0)) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS wins_tournament,
            SUM(CASE WHEN (dm.games < IFNULL(odm.games, 0)) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS losses_tournament,
            SUM(CASE WHEN (dm.games = IFNULL(odm.games, 0)) AND (ct.name = 'Gatherling') THEN 1 ELSE 0 END) AS draws_tournament
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
        {competition_join}
        {season_join}
        GROUP BY
            a.id,
            oa.id,
            d.person_id,
            season.id
    """.format(table=table, competition_join=query.competition_join(), season_join=query.season_join())
    preaggregation.preaggregate(table, sql)

@retry_after_calling(preaggregate)
def load_matchups(where: str = 'TRUE', archetype_id: Optional[int] = None, person_id: Optional[int] = None, season_id: Optional[int] = None) -> List[Container]:
    if person_id:
        table = '_matchup_ps_stats'
        where = f'({where}) AND (mps.person_id = {person_id})'
    else:
        table = '_matchup_stats'
    if archetype_id:
        where = f'({where}) AND (a.id = {archetype_id})'
    sql = """
        SELECT
            archetype_id,
            a.name AS archetype_name,
            opponent_archetype_id AS id,
            oa.name AS name,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            SUM(wins_tournament) AS wins_tournament,
            SUM(losses_tournament) AS losses_tournament,
            SUM(draws_tournament) AS draws_tournament,
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS win_percent,
            IFNULL(ROUND((SUM(wins_tournament) / NULLIF(SUM(wins_tournament + losses_tournament), 0)) * 100, 1), '') AS win_percent_tournament
        FROM
            {table} AS mps
        INNER JOIN
            archetype AS a ON archetype_id = a.id
        INNER JOIN
            archetype AS oa ON opponent_archetype_id = oa.id
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            archetype_id,
            opponent_archetype_id
        ORDER BY
            wins DESC,
            oa.name
    """.format(table=table, where=where, season_query=query.season_query(season_id))
    return [Container(m) for m in db().select(sql)]

@retry_after_calling(preaggregate)
def load_archetypes_deckless(order_by: str = '`num_decks` DESC, `wins` DESC, name', person_id: Optional[int] = None, season_id: Optional[int] = None) -> List[Archetype]:
    if person_id:
        table = '_arch_person_stats'
        where = 'person_id = {person_id}'.format(person_id=sqlescape(person_id))
        group_by = 'ars.person_id, a.id'
    else:
        table = '_archetype_stats'
        where = 'TRUE'
        group_by = 'a.id'
    sql = """
        SELECT
            a.id,
            a.name,
            a.description,
            aca.ancestor AS parent_id,
            SUM(num_decks) AS num_decks,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            SUM(wins - losses) AS record,
            SUM(num_decks_tournament) AS num_decks_tournament,
            SUM(wins_tournament) AS wins_tournament,
            SUM(losses_tournament) AS losses_tournament,
            SUM(draws_tournament) AS draws_tournament,
            SUM(wins_tournament - losses_tournament) AS record_tournament,
            SUM(perfect_runs) AS perfect_runs,
            SUM(tournament_wins) AS tournament_wins,
            SUM(tournament_top8s) AS tournament_top8s,
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS win_percent,
            IFNULL(ROUND((SUM(wins_tournament) / NULLIF(SUM(wins_tournament + losses_tournament), 0)) * 100, 1), '') AS win_percent_tournament
        FROM
            archetype AS a
        LEFT JOIN
            {table} AS ars ON a.id = ars.archetype_id
        LEFT JOIN
            archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            {group_by},
            aca.ancestor -- aca.ancestor will be unique per a.id because of integrity constraints enforced elsewhere (each archetype has one ancestor) but we let the database know here.
        ORDER BY
            {order_by}
    """.format(table=table, where=where, group_by=group_by, season_query=query.season_query(season_id), order_by=order_by)
    archetypes = [Archetype(a) for a in db().select(sql)]
    archetypes_by_id = {a.id: a for a in archetypes}
    for a in archetypes:
        a.decks = []
        a.decks_tournament = []
        a.parent = archetypes_by_id.get(a.parent_id, None)
    return preorder(archetypes)

def preorder(archetypes: List[Archetype]):
    archs = []
    roots = [a for a in archetypes if a.is_root]
    for r in roots:
        for a in PreOrderIter(r):
            archs.append(a)
    return archs
