from typing import TypedDict

import titlecase
from anytree import NodeMixin
from anytree.iterators import PreOrderIter

from decksite.data import clauses, deck, preaggregation, query
from decksite.database import db
from magic.models import Competition
from shared import redis_wrapper as redis
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import retry_after_calling
from shared.pd_exception import DoesNotExistException


class Archetype(Container, NodeMixin):
    pass


class SeasonStats(TypedDict):
    meta_share: float
    win_rate: float | None


BASE_ARCHETYPES: dict[Archetype, Archetype] = {}

# The length of each of the two periods movers and shakers compares. A week is short enough that
# what it shows is news and long enough that most archetypes clear the minimum match count.
WINDOW_DAYS = 7

# Matches needed in one of the two windows before an archetype can be a mover. Because an archetype's
# change in meta share is bounded by its meta share, a rare archetype cannot move far enough to reach
# the top or bottom of the list anyway, and in practice anything from 1 to 15 picks the same
# archetypes. This is set to a little more than a single 5-round league run purely as a floor against
# a freak low-volume week.
MIN_MATCHES = 6

def load_archetype(archetype: int | str) -> Archetype:
    try:
        archetype_id = int(archetype)
    except ValueError as c:
        name = titlecase.titlecase(archetype)
        name_without_dashes = name.replace('-', ' ')
        archetype_id = db().value("SELECT id FROM archetype WHERE REPLACE(REPLACE(name, ' // ', ' / '), '-', ' ') = %s", [name_without_dashes])
        if not archetype_id:
            raise DoesNotExistException(f'Did not find archetype with name of `{name}`') from c
    arch = Archetype()
    arch.id = int(archetype_id)
    arch.name = db().value('SELECT name FROM archetype WHERE id = %s', [archetype_id])
    return arch

def load_competition_archetypes(competition_id: int) -> list[Archetype]:
    sql = f"""
        SELECT
            a.id,
            a.name,
            aca.ancestor AS parent_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(dsum.wins), 0) AS wins,
            IFNULL(SUM(dsum.losses), 0) AS losses,
            IFNULL(SUM(dsum.draws), 0) AS draws,
            SUM(IFNULL(dsum.wins, 0) - IFNULL(dsum.losses, 0)) AS record,
            SUM(CASE WHEN dsum.wins >= 5 AND dsum.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type,
            CAST(ROUND((SUM(dsum.wins) / NULLIF(SUM(dsum.wins + dsum.losses), 0)) * 100, 1) AS DOUBLE) AS win_percent,
            COUNT(*) OVER () AS total
        FROM
            archetype AS a
        LEFT JOIN
            archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        LEFT JOIN
            deck AS d ON a.id = d.archetype_id
        {query.competition_join()}
        {query.season_join()}
        {deck.nwdl_join()}
        WHERE
            competition_id = {competition_id}
        GROUP BY
            a.id
        ORDER BY
            num_decks DESC,
            name
    """
    archs, _ = archetype_list_from(sql, True)
    return archs

def seasons_active(archetype_id: int) -> list[int]:
    sql = 'SELECT season_id FROM _arch_stats WHERE archetype_id = %s'
    return db().values(sql, [archetype_id])

def season_stats(archetype_id: int, tournament_only: bool = False) -> list[SeasonStats]:
    where = 'TRUE'
    if tournament_only:
        where = "deck_type = 'tournament'"
    sql = f"""
        WITH season_totals AS (
            SELECT
                season.id AS season_id,
                IFNULL(SUM(wins + losses + draws), 0) AS num_matches
            FROM
                season
            LEFT JOIN
                _arch_stats AS a ON a.season_id = season.id AND archetype_id <= 9 AND {where}
            GROUP BY
                season.id
        )
        SELECT
            CASE WHEN st.num_matches = 0 THEN 0 ELSE SUM(a.wins + a.losses + a.draws) / st.num_matches END AS meta_share,
            SUM(a.wins) / NULLIF(SUM(a.wins + a.losses), 0) AS win_rate
        FROM
            season_totals AS st
        LEFT JOIN
            _arch_stats AS a ON a.season_id = st.season_id AND a.archetype_id = %s AND {where}
        GROUP BY
            st.season_id
        ORDER BY
            st.season_id;
    """
    return [
        {
            'meta_share': float(row['meta_share']) if row['meta_share'] else 0.0,
            'win_rate': float(row['win_rate']) if row['win_rate'] is not None else None,
        }
        for row in db().select(sql, [archetype_id])
    ]

def add(name: str, parent: int, description: str) -> None:
    archetype_id = db().insert('INSERT INTO archetype (name, description) VALUES (%s, %s)', [name, description])
    ancestors = db().select('SELECT ancestor, depth FROM archetype_closure WHERE descendant = %s', [parent])
    sql = 'INSERT INTO archetype_closure (ancestor, descendant, depth) VALUES '
    for a in ancestors:
        sql += '({ancestor}, {descendant}, {depth}), '.format(ancestor=sqlescape(a['ancestor']), descendant=archetype_id, depth=int(a['depth']) + 1)
    sql += f'({archetype_id}, {archetype_id}, 0)'
    db().execute(sql)

def assign(deck_id: int, archetype_id: int, person_id: int | None, reviewed: bool = True, similarity: int | None = None) -> None:
    db().begin('assign_archetype')
    db().execute('INSERT INTO deck_archetype_change (changed_date, deck_id, archetype_id, person_id) VALUES (UNIX_TIMESTAMP(NOW()), %s, %s, %s)', [deck_id, archetype_id, person_id])
    and_clause = '' if reviewed else 'AND reviewed is FALSE'
    db().execute(f'UPDATE deck SET reviewed = %s, archetype_id = %s WHERE id = %s {and_clause}', [reviewed, archetype_id, deck_id])
    if not reviewed and similarity is not None:
        db().execute('UPDATE deck_cache SET similarity = %s WHERE deck_id = %s', [similarity, deck_id])
    db().commit('assign_archetype')
    redis.clear(f'decksite:deck:{deck_id}')

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

def base_archetypes() -> list[Archetype]:
    return [a for a in base_archetype_by_id().values() if a.parent is None]

def base_archetype_by_id() -> dict[Archetype, Archetype]:
    if len(BASE_ARCHETYPES) == 0:
        rebuild_archetypes()
    return BASE_ARCHETYPES

def base_archetypes_data(c: Competition) -> dict[str, int]:
    base_archs_by_id = base_archetype_by_id()
    if not c.base_archetype_data:
        c.base_archetype_data = {a.name: 0 for a in base_archetypes()}
        for d in c.decks:
            if not d.archetype_id:
                continue
            base_archetype_name = base_archs_by_id[d.archetype_id].name
            c.base_archetype_data[base_archetype_name] += 1
    return c.base_archetype_data

def rebuild_archetypes() -> None:
    archetypes_by_id = {a.id: a for a in load_archetypes()}
    for k, v in archetypes_by_id.items():
        p = v
        while p.parent is not None:
            p = p.parent
        BASE_ARCHETYPES[k] = p

def preaggregate() -> None:
    preaggregate_archetypes()
    preaggregate_archetype_person()
    preaggregate_disjoint_archetypes()
    preaggregate_disjoint_archetype_person()
    preaggregate_matchups()
    preaggregate_matchups_person()
    preaggregate_archetype_days()

def preaggregate_archetypes() -> None:
    table = '_arch_stats'
    sql = f"""
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
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (season_id, archetype_id, deck_type),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            season.season_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(dsum.wins), 0) AS wins,
            IFNULL(SUM(dsum.losses), 0) AS losses,
            IFNULL(SUM(dsum.draws), 0) AS draws,
            SUM(CASE WHEN dsum.wins >= 5 AND dsum.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
        FROM
            archetype AS a
        LEFT JOIN
            archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        LEFT JOIN
            archetype_closure AS acd ON a.id = acd.ancestor
        LEFT JOIN
            deck AS d ON acd.descendant = d.archetype_id
        {query.competition_join()}
        {query.season_join()}
        {deck.nwdl_join()}
        GROUP BY
            a.id,
            aca.ancestor, -- aca.ancestor will be unique per a.id because of integrity constraints enforced elsewhere (each archetype has one ancestor) but we let the database know here.
            season.season_id,
            ct.name
        HAVING
            season.season_id IS NOT NULL
    """
    preaggregation.preaggregate(table, sql)

def preaggregate_archetype_person() -> None:
    # This preaggregation fails if I use the obvious name _archetype_person_stats but works with any other name. It's confusing.
    table = '_arch_person_stats'
    sql = f"""
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
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (person_id, season_id, archetype_id, deck_type),
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            d.person_id,
            season.season_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(dsum.wins), 0) AS wins,
            IFNULL(SUM(dsum.losses), 0) AS losses,
            IFNULL(SUM(dsum.draws), 0) AS draws,
            SUM(CASE WHEN dsum.wins >= 5 AND dsum.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
        FROM
            archetype AS a
        LEFT JOIN
            archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        LEFT JOIN
            archetype_closure AS acd ON a.id = acd.ancestor
        LEFT JOIN
            deck AS d ON acd.descendant = d.archetype_id
        {query.competition_join()}
        {query.season_join()}
        {deck.nwdl_join()}
        GROUP BY
            a.id,
            d.person_id,
            season.season_id,
            ct.name
        HAVING
            season.season_id IS NOT NULL
    """
    preaggregation.preaggregate(table, sql)

def preaggregate_disjoint_archetypes() -> None:
    table = '_arch_disjoint_stats'
    sql = f"""
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
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (season_id, archetype_id, deck_type),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            season.season_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(dsum.wins), 0) AS wins,
            IFNULL(SUM(dsum.losses), 0) AS losses,
            IFNULL(SUM(dsum.draws), 0) AS draws,
            SUM(CASE WHEN dsum.wins >= 5 AND dsum.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
        FROM
            archetype AS a
        LEFT JOIN
            deck AS d ON a.id = d.archetype_id
        {query.competition_join()}
        {query.season_join()}
        {deck.nwdl_join()}
        GROUP BY
            a.id,
            season.season_id,
            ct.name
        HAVING
            season.season_id IS NOT NULL
    """
    preaggregation.preaggregate(table, sql)

def preaggregate_disjoint_archetype_person() -> None:
    table = '_arch_disjoint_person_stats'
    sql = f"""
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
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (person_id, season_id, archetype_id, deck_type),
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            d.person_id,
            season.season_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(dsum.wins), 0) AS wins,
            IFNULL(SUM(dsum.losses), 0) AS losses,
            IFNULL(SUM(dsum.draws), 0) AS draws,
            SUM(CASE WHEN dsum.wins >= 5 AND dsum.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
        FROM
            archetype AS a
        LEFT JOIN
            deck AS d ON a.id = d.archetype_id
        {query.competition_join()}
        {query.season_join()}
        {deck.nwdl_join()}
        GROUP BY
            a.id,
            d.person_id,
            season.season_id,
            ct.name
        HAVING
            season.season_id IS NOT NULL
    """
    preaggregation.preaggregate(table, sql)

# Disjoint archetype stats bucketed by the UTC day a match was played on, so that we can compare
# recent form against the immediately preceding period. Unlike the other archetype preaggregates
# this is keyed on match date rather than deck creation date, because "what happened this week" is a
# question about matches, not about when a decklist was first uploaded.
def preaggregate_archetype_days() -> None:
    table = '_arch_day_stats'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            archetype_id INT NOT NULL,
            season_id INT NOT NULL,
            day INT NOT NULL,
            num_decks INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (season_id, day, archetype_id, deck_type),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            d.archetype_id,
            season.season_id,
            FLOOR(m.date / 86400) * 86400 AS day,
            COUNT(DISTINCT d.id) AS num_decks,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins, -- IFNULL so we still count byes as wins.
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
        FROM
            `match` AS m
        INNER JOIN
            deck_match AS dm ON dm.match_id = m.id
        INNER JOIN
            deck_match AS odm ON odm.match_id = m.id AND odm.deck_id <> dm.deck_id
        INNER JOIN
            deck AS d ON d.id = dm.deck_id
        {query.competition_join()}
        {query.season_join()}
        GROUP BY
            d.archetype_id,
            season.season_id,
            day,
            ct.name
        HAVING
            season_id IS NOT NULL AND archetype_id IS NOT NULL
    """
    preaggregation.preaggregate(table, sql)

def preaggregate_matchups() -> None:
    table = '_matchup_stats'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            archetype_id INT NOT NULL,
            opponent_archetype_id INT NOT NULL,
            season_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (season_id, archetype_id, opponent_archetype_id, deck_type),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (opponent_archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            oa.id AS opponent_archetype_id,
            season.season_id,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins, -- IFNULL so we still count byes as wins.
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
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
        {query.competition_join()}
        {query.season_join()}
        GROUP BY
            a.id,
            oa.id,
            season.season_id,
            ct.name
    """
    preaggregation.preaggregate(table, sql)

def preaggregate_matchups_person() -> None:
    table = '_matchup_ps_stats'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            archetype_id INT NOT NULL,
            opponent_archetype_id INT NOT NULL,
            person_id INT NOT NULL,
            season_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (season_id, archetype_id, opponent_archetype_id, person_id, deck_type),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (opponent_archetype_id) REFERENCES archetype (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            a.id AS archetype_id,
            oa.id AS opponent_archetype_id,
            d.person_id,
            season.season_id,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins, -- IFNULL so we still count byes as wins.
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
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
        {query.competition_join()}
        {query.season_join()}
        GROUP BY
            a.id,
            oa.id,
            d.person_id,
            season.season_id,
            ct.name
    """
    preaggregation.preaggregate(table, sql)

@retry_after_calling(preaggregate)
def load_matchups(where: str = 'TRUE', archetype_id: int | None = None, person_id: int | None = None, season_id: int | None = None, tournament_only: bool = False) -> list[Container]:
    if person_id:
        table = '_matchup_ps_stats'
        where = f'({where}) AND (mps.person_id = {person_id})'
    else:
        table = '_matchup_stats'
    if archetype_id:
        where = f'({where}) AND (a.id = {archetype_id})'
    if tournament_only:
        where = f"({where}) AND (mps.deck_type = 'tournament')"
    sql = f"""
        SELECT
            archetype_id,
            a.name AS archetype_name,
            opponent_archetype_id AS id,
            oa.name AS name,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            CAST(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1) AS DOUBLE) AS win_percent
        FROM
            {table} AS mps
        INNER JOIN
            archetype AS a ON archetype_id = a.id
        INNER JOIN
            archetype AS oa ON opponent_archetype_id = oa.id
        WHERE
            ({where}) AND ({query.season_query(season_id)})
        GROUP BY
            archetype_id,
            opponent_archetype_id
        ORDER BY
            wins DESC,
            oa.name
    """
    return [Container(m) for m in db().select(sql)]

@retry_after_calling(preaggregate)
def load_archetypes(order_by: str | None = None, person_id: int | None = None, season_id: int | None = None, tournament_only: bool = False) -> list[Archetype]:
    if person_id:
        table = '_arch_person_stats'
        where = f'person_id = {sqlescape(person_id)}'
        group_by = 'ars.person_id, a.id'
    else:
        table = '_arch_stats'
        where = 'TRUE'
        group_by = 'a.id'
    if tournament_only:
        where = f"({where}) AND deck_type = 'tournament'"
    sql = """
        SELECT
            a.id,
            a.name,
            a.description,
            aca.ancestor AS parent_id,
            IFNULL(SUM(num_decks), 0) AS num_decks,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            SUM(wins - losses) AS record,
            SUM(perfect_runs) AS perfect_runs,
            SUM(tournament_wins) AS tournament_wins,
            SUM(tournament_top8s) AS tournament_top8s,
            CAST(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1) AS DOUBLE) AS win_percent,
            COUNT(*) OVER () AS total
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
    """.format(table=table, where=where, group_by=group_by, season_query=query.season_query(season_id), order_by=order_by or 'TRUE')
    archs, _ = archetype_list_from(sql, order_by is None)
    return archs

# Load a list of all archetypes where archetypes categories do NOT include the stats of their children. Thus Aggro is only decks assigned directly to Aggro and does not include Red Deck Wins. See also load_archetypes that does it the other way.
@retry_after_calling(preaggregate)
def load_disjoint_archetypes(where: str = 'TRUE', order_by: str | None = None, limit: str = '', person_id: int | None = None, season_id: int | None = None, tournament_only: bool = False) -> tuple[list[Archetype], int]:
    if person_id:
        table = '_arch_disjoint_person_stats'
        base_where = f'person_id = {sqlescape(person_id)}'
        group_by = 'ars.person_id, a.id'
    else:
        table = '_arch_disjoint_stats'
        base_where = 'TRUE'
        group_by = 'a.id'
    rank_where = "deck_type = 'tournament'" if tournament_only else 'TRUE'
    if tournament_only:
        base_where = f"({base_where}) AND deck_type = 'tournament'"
    where = f'({where}) AND ({base_where})'
    season_query = query.season_query(season_id)
    order_by = order_by or 'TRUE'
    sql = f"""
        WITH total_count AS (
            SELECT
                SUM(wins + draws + losses) AS total_matches
            FROM
                archetype AS a
            LEFT JOIN
                {table} AS ars ON a.id = ars.archetype_id
            LEFT JOIN
                archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
            WHERE
                ({base_where}) AND ({season_query})
        ),
        season_ranks AS (
            SELECT
                a.id AS archetype_id,
                RANK() OVER (ORDER BY {clauses.wilson_lower_bound_sql()} DESC) AS quality_rank
            FROM
                archetype AS a
            LEFT JOIN
                _arch_disjoint_stats AS ars ON a.id = ars.archetype_id
            LEFT JOIN
                archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
            WHERE
                ({rank_where}) AND ({season_query})
            GROUP BY
                a.id, aca.ancestor
        )
        SELECT
            a.id,
            a.name,
            a.description,
            aca.ancestor AS parent_id,
            IFNULL(SUM(num_decks), 0) AS num_decks,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            SUM(wins - losses) AS record,
            SUM(perfect_runs) AS perfect_runs,
            SUM(tournament_wins) AS tournament_wins,
            SUM(tournament_top8s) AS tournament_top8s,
            CAST(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1) AS DOUBLE) AS win_percent,
            COUNT(*) OVER () AS total,
            SUM(wins + losses + draws) / tc.total_matches AS meta_share,
            {clauses.wilson_lower_bound_sql()} AS quality_score,
            sr.quality_rank
        FROM
            archetype AS a
        LEFT JOIN
            {table} AS ars ON a.id = ars.archetype_id
        LEFT JOIN
             archetype_closure AS aca ON a.id = aca.descendant AND aca.depth = 1
        LEFT JOIN
            total_count AS tc ON TRUE
        LEFT JOIN
            season_ranks AS sr ON a.id = sr.archetype_id
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            {group_by},
            aca.ancestor -- aca.ancestor will be unique per a.id because of integrity constraints enforced elsewhere (each archetype has one ancestor) but we let the database know here.
        ORDER BY
            {order_by}
        {limit}
    """
    return archetype_list_from(sql, order_by is None)

# Archetypes whose share of the metagame has moved most over the last `window_days` days of the
# season, compared against the `window_days` immediately before that. /metagame has no time axis, so
# this is the one thing the home page can say about the metagame that a link to /metagame cannot.
# Both windows are clamped to the season, so nothing from the previous season leaks in over rotation.
@retry_after_calling(preaggregate)
def load_movers_and_shakers(season_id: int, window_days: int = WINDOW_DAYS, min_matches: int = MIN_MATCHES) -> list[Archetype]:
    window = window_days * 60 * 60 * 24
    season_query = query.season_query(season_id)
    sql = f"""
        WITH bounds AS (
            -- One day past the most recent day with any matches in this season. For the current
            -- season that is tomorrow; for a past season it is the day after the season ended.
            SELECT
                MAX(day) + 86400 AS end_date
            FROM
                _arch_day_stats
            WHERE
                {season_query}
        ),
        windows AS (
            SELECT
                ads.archetype_id,
                SUM(CASE WHEN ads.day >= b.end_date - {window} THEN ads.wins + ads.losses + ads.draws ELSE 0 END) AS num_matches,
                SUM(CASE WHEN ads.day >= b.end_date - {window} THEN ads.wins ELSE 0 END) AS wins,
                SUM(CASE WHEN ads.day >= b.end_date - {window} THEN ads.losses ELSE 0 END) AS losses,
                SUM(CASE WHEN ads.day >= b.end_date - {window} THEN ads.draws ELSE 0 END) AS draws,
                SUM(CASE WHEN ads.day < b.end_date - {window} THEN ads.wins + ads.losses + ads.draws ELSE 0 END) AS previous_num_matches
            FROM
                _arch_day_stats AS ads
            CROSS JOIN
                bounds AS b
            WHERE
                ({season_query}) AND ads.day >= b.end_date - {window * 2} AND ads.day < b.end_date
            GROUP BY
                ads.archetype_id
        ),
        totals AS (
            SELECT
                SUM(num_matches) AS total_matches,
                SUM(previous_num_matches) AS previous_total_matches
            FROM
                windows
        )
        SELECT
            a.id,
            a.name,
            w.num_matches,
            w.wins,
            w.losses,
            w.draws,
            CAST(ROUND((w.wins / NULLIF(w.wins + w.losses, 0)) * 100, 1) AS DOUBLE) AS win_percent,
            w.num_matches / t.total_matches AS meta_share,
            w.num_matches / t.total_matches - (CASE WHEN t.previous_total_matches > 0 THEN w.previous_num_matches / t.previous_total_matches ELSE 0 END) AS meta_share_change
        FROM
            windows AS w
        INNER JOIN
            archetype AS a ON a.id = w.archetype_id
        CROSS JOIN
            totals AS t
        WHERE
            -- Either window will do: an archetype that played 90 matches last week and 11 this week
            -- is the most interesting faller there is, and a floor on the current window alone would
            -- be exactly the thing that hid it.
            GREATEST(w.num_matches, w.previous_num_matches) >= {min_matches}
        ORDER BY
            meta_share_change DESC, w.num_matches DESC, a.name
    """
    return [Archetype(r) for r in db().select(sql)]

def archetype_list_from(sql: str, should_preorder: bool) -> tuple[list[Archetype], int]:
    rs = db().select(sql)
    archetypes = [Archetype({k: v for k, v in a.items() if k != 'total'}) for a in rs]
    archetypes_by_id = {a.id: a for a in archetypes}
    for a in archetypes:
        a.decks = []
        a.decks_tournament = []
        a.parent = archetypes_by_id.get(a.parent_id, None)
    if should_preorder:
        archetypes = preorder(archetypes)
    return archetypes, 0 if not rs else rs[0]['total']

def preorder(archetypes: list[Archetype]) -> list[Archetype]:
    archs = []
    roots = [a for a in archetypes if a.is_root]
    for r in roots:
        for a in PreOrderIter(r):
            archs.append(a)
    return archs

def load_archetype_tree() -> list[dict]:
    sql = """
        SELECT a.name AS name, b.name AS ancestor
        FROM decksite.archetype AS a
        LEFT JOIN decksite.archetype_closure AS cl
        ON cl.descendant = a.id AND cl.depth = 1
        LEFT JOIN decksite.archetype AS b
        ON cl.ancestor = b.id
    """
    return db().select(sql)
