import re
from typing import TYPE_CHECKING, Dict, List, Optional, cast

from flask import url_for
from flask_babel import gettext, ngettext

import decksite
from decksite.data import deck, query
from decksite.database import db
from magic import tournaments
from magic.models import Deck
from shared.container import Container
from shared.decorators import retry_after_calling

if TYPE_CHECKING:
    from decksite.data import person # pylint:disable=unused-import

LEADERBOARD_TOP_N = 5
LEADERBOARD_LIMIT = 12

def load_achievements(p: Optional['person.Person'], season_id: Optional[int], with_detail: bool = False) -> List[Container]:
    achievements = []
    for a in Achievement.all_achievements:
        desc = Container({'title': a.title, 'description_safe': a.description_safe})
        desc.summary = a.load_summary(season_id=season_id)
        desc.legend = a.display(p) if p else ''
        if with_detail:
            desc.detail = a.detail(p, season_id=season_id)
        else:
            desc.percent = a.percent(season_id=season_id)
            desc.leaderboard = a.leaderboard(season_id=season_id)
            desc.leaderboard_heading = a.leaderboard_heading()
        achievements.append(desc)
    if with_detail:
        return achievements
    return sorted(achievements, key=lambda ad: -ad.percent)

def load_query(people_by_id: Dict[int, 'person.Person'], season_id: Optional[int]) -> str:
    # keys have been normalised earlier but could still be reserved words
    columns = ', '.join(f'SUM(`{a.key}`) as `{a.key}`' for a in Achievement.all_achievements if a.in_db)
    return """
        SELECT
            person_id AS id,
            {columns}
        FROM
            _achievements AS a
        WHERE
            person_id IN ({ids}) AND ({season_query})
        GROUP BY
            person_id
    """.format(columns=columns, ids=', '.join(str(k) for k in people_by_id.keys()), season_query=query.season_query(season_id))

def preaggregate_achievements() -> None:
    db().execute('DROP TABLE IF EXISTS _new_achievements')
    db().execute(preaggregate_query())
    db().execute('DROP TABLE IF EXISTS _old_achievements')
    db().execute('CREATE TABLE IF NOT EXISTS _achievements (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _achievements TO _old_achievements, _new_achievements TO _achievements')
    db().execute('DROP TABLE IF EXISTS _old_achievements')

def preaggregate_query() -> str:
    # mypy doesn't understand our contract that a.create_columns etc. are only None if in_db is False
    create_columns = ', '.join(cast(str, a.create_columns) for a in Achievement.all_achievements if a.in_db)
    select_columns = ', '.join(cast(str, a.select_columns) for a in Achievement.all_achievements if a.in_db)
    with_clauses = ', '.join(a.with_sql for a in Achievement.all_achievements if a.with_sql is not None)
    join_clauses = ' '.join(a.join_sql for a in Achievement.all_achievements if a.join_sql is not None)
    return """
        CREATE TABLE IF NOT EXISTS _new_achievements (
            person_id INT NOT NULL,
            season_id INT NOT NULL,
            {cc},
            PRIMARY KEY (season_id, person_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        WITH
        {with_clauses}
        SELECT
            p.id AS person_id,
            season.id AS season_id,
            {sc}
        FROM
            person AS p
        LEFT JOIN
            deck AS d ON d.person_id = p.id
        LEFT JOIN
            deck_cache AS dc ON dc.deck_id = d.id
        {season_join}
        {competition_join}
        {join_clauses}
        GROUP BY
            p.id,
            season.id
        HAVING
            season.id IS NOT NULL
    """.format(cc=create_columns, sc=select_columns, with_clauses=with_clauses, join_clauses=join_clauses, season_join=query.season_join(), competition_join=query.competition_join())

# Abstract achievement classes

class Achievement:
    all_achievements: List['Achievement'] = []
    in_db = True
    key: Optional[str] = None
    title = ''
    flags: List[str] = []

    @property
    def description_safe(self) -> str:
        return ''

    @property
    def sql(self) -> Optional[str]:
        return None

    @property
    def with_sql(self) -> Optional[str]:
        return None

    @property
    def join_sql(self) -> Optional[str]:
        return None

    @property
    def detail_sql(self) -> Optional[str]:
        return None

    @property
    def create_columns(self) -> Optional[str]:
        if not self.in_db:
            return None
        if self.detail_sql is None:
            return f'`{self.key}` INT NOT NULL'
        return f'`{self.key}` INT NOT NULL, `{self.key}_detail` LONGTEXT DEFAULT NULL'

    @property
    def select_columns(self) -> Optional[str]:
        if not self.in_db:
            return None
        if self.detail_sql is None:
            return f'{self.sql} AS `{self.key}`'
        return f'{self.sql} AS `{self.key}`, {self.detail_sql} AS `{self.key}_detail`'

    def __init_subclass__(cls) -> None:
        if cls.key is not None:
            # in case anyone ever makes a poor sportsmanship achievement called DROP TABLE
            cls.key = re.sub('[^A-Za-z0-9_]+', '', cls.key)
            if cls.key in [c.key for c in cls.all_achievements]:
                print(f"Warning: Two achievements have the same normalised key {cls.key}. This won't do any permanent damage to the database but the results are almost certainly not as intended.")
            # pylint can't determine that we have verified cls.key to be a str
            if cls.key[-7:] == '_detail': #pylint: disable=unsubscriptable-object
                print(f"Warning: achievement key {cls.key} should not end with the string '_detail'.")
            cls.all_achievements.append(cls())

    # pylint: disable=no-self-use, unused-argument
    def display(self, p: 'person.Person') -> str:
        return ''

    # Note: load_summary must be overridden if in_db=False!
    @retry_after_calling(preaggregate_achievements)
    def load_summary(self, season_id: Optional[int] = None) -> Optional[str]:
        season_condition = query.season_query(season_id)
        sql = f'SELECT SUM(`{self.key}`) AS num, COUNT(DISTINCT person_id) AS pnum FROM _achievements WHERE `{self.key}` > 0 AND {season_condition}'
        for r in db().select(sql):
            res = Container(r)
            if res.num is None:
                return 'Not earned by any players.'
            times_text = ngettext(' once', f' %(num)d times', res.num) if res.num > res.pnum else ''
            players_text = ngettext('1 player', f'%(num)d players', res.pnum)
            return f'Earned{times_text} by {players_text}.'
        return None

    @retry_after_calling(preaggregate_achievements)
    def percent(self, season_id: Optional[int] = None) -> float:
        season_condition = query.season_query(season_id)
        sql = f'SELECT SUM(CASE WHEN {self.key} > 0 THEN 1 ELSE 0 END) AS pnum, COUNT(*) AS mnum FROM _achievements WHERE {season_condition}'
        r = db().select(sql)[0]
        try:
            return int(r['pnum'] or 0) * 100.0 / int(r['mnum'])
        except ZeroDivisionError:
            return 0

    @retry_after_calling(preaggregate_achievements)
    def detail(self, p: 'person.Person', season_id: Optional[int] = None) -> Optional[List[Deck]]:
        if self.detail_sql is None:
            return None
        sql = """
                SELECT
                    GROUP_CONCAT({k}_detail)
                FROM
                    _achievements
                WHERE
                    person_id={id} AND {season_query}
                GROUP BY
                    person_id
            """.format(k=self.key, id=p.id, season_query=query.season_query(season_id))
        ids = db().value(sql)
        result = Container()
        result.decks = deck.load_decks(where=f'd.id IN ({ids})') if ids is not None else []
        for f in self.flags:
            result[f] = True
        return result

    def leaderboard(self, season_id: Optional[int] = None) -> Optional[List[Container]]:
        season_condition = query.season_query(season_id)
        person_query = query.person_query()
        sql = f"""
            SELECT
                {person_query} AS person,
                SUM({self.key}) AS points,
                p.id AS person_id
            FROM
                person AS p
            JOIN
                _achievements
            ON
                p.id = _achievements.person_id
            WHERE
                {season_condition}
            GROUP BY
                p.id
            HAVING
                points >=
                    (   -- Work out the minimum score to make top N, counting ties
                        SELECT
                            MIN(s)
                        FROM
                            (
                                SELECT
                                    SUM({self.key}) AS s
                                FROM
                                    _achievements
                                WHERE
                                    {season_condition}
                                GROUP BY
                                    person_id
                                HAVING
                                    s > 0
                                ORDER BY
                                    s DESC
                                LIMIT
                                    {LEADERBOARD_TOP_N}
                            ) AS _
                    )
            ORDER BY
                points DESC,
                name
            LIMIT {LEADERBOARD_LIMIT}
        """
        leaderboard = []
        for row in db().select(sql):
            c = Container(row)
            c.score = c.points
            leaderboard.append(c)

        return leaderboard if len(leaderboard) > 0 else None

    # pylint: disable=no-self-use
    def leaderboard_heading(self) -> str:
        return ''

class CountedAchievement(Achievement):
    def display(self, p: 'person.Person') -> str:
        n = p.get('achievements', {}).get(self.key, 0)
        if n > 0:
            return self.localised_display(n)
        return ''

    def leaderboard_heading(self) -> str:
        raise NotImplementedError()

    def localised_display(self, n: int) -> str:
        """Calls and returns ngettext."""
        raise NotImplementedError()

class BooleanAchievement(Achievement):
    season_text = ''

    @staticmethod
    def alltime_text(_: int) -> str:
        return ''

    def display(self, p: 'person.Person') -> str:
        n = p.get('achievements', {}).get(self.key, 0)
        if n > 0:
            if decksite.get_season_id() == 'all':
                return self.alltime_text(n)
            return self.season_text
        return ''

    # No point showing a leaderboard for these on single-season page because no-one can have more than 1
    def leaderboard(self, season_id: Optional[int] = None) -> Optional[List[Container]]:
        if season_id == 'all':
            return super(BooleanAchievement, self).leaderboard(season_id=season_id)
        return None

    def leaderboard_heading(self) -> str:
        return gettext('Seasons')

class TournamentOrganizer(Achievement):
    in_db = False
    key = 'tournament_organizer'
    title = 'Tournament Organizer'
    description_safe = 'Run a tournament for the Penny Dreadful community.'

    def __init__(self) -> None:
        self.hosts = [host for series in tournaments.all_series_info() for host in series['hosts']]

    def display(self, p: 'person.Person') -> str:
        if p.name in self.hosts:
            return 'Tournament Run'
        return ''

    def load_summary(self, season_id: Optional[int] = None) -> Optional[str]:
        # We can't give per-season stats for this because they don't exist
        clarification = ' (all-time)' if season_id != 'all' else ''
        return f'Earned by {len(self.hosts)} players{clarification}.'

    @retry_after_calling(preaggregate_achievements)
    def percent(self, season_id: Optional[int] = None) -> float: # pylint: disable=unused-argument
        sql = f'SELECT COUNT(*) AS mnum FROM _achievements'
        r = db().select(sql)[0]
        return len(self.hosts) * 100.0 / int(r['mnum'])

    def leaderboard(self, season_id: Optional[int] = None) -> Optional[List[Container]]:
        return None

class TournamentPlayer(CountedAchievement):
    key = 'tournament_entries'
    title = 'Tournament Player'
    sql = "COUNT(DISTINCT CASE WHEN ct.name = 'Gatherling' THEN d.id ELSE NULL END)"
    detail_sql = "GROUP_CONCAT(DISTINCT CASE WHEN ct.name = 'Gatherling' THEN d.id ELSE NULL END)"
    flags = ['hide_person', 'hide_source']

    @property
    def description_safe(self) -> str:
        return 'Play in an official Penny Dreadful tournament on <a href="https://gatherling.com/">gatherling.com</a>'

    def leaderboard_heading(self) -> str:
        return gettext('Tournaments')

    def localised_display(self, n: int) -> str:
        return ngettext('1 tournament entered', '%(num)d tournaments entered', n)

class TournamentWinner(CountedAchievement):
    key = 'tournament_wins'
    title = 'Tournament Winner'
    description_safe = 'Win a tournament.'
    sql = "COUNT(DISTINCT CASE WHEN d.finish = 1 AND ct.name = 'Gatherling' THEN d.id ELSE NULL END)"
    detail_sql = "GROUP_CONCAT(DISTINCT CASE WHEN d.finish = 1 AND ct.name = 'Gatherling' THEN d.id ELSE NULL END)"
    flags = ['hide_person', 'hide_source']

    def leaderboard_heading(self) -> str:
        return gettext('Victories')

    def localised_display(self, n: int) -> str:
        return ngettext('1 victory', '%(num)d victories', n)

class LeaguePlayer(CountedAchievement):
    key = 'league_entries'
    title = 'League Player'
    sql = "COUNT(DISTINCT CASE WHEN ct.name = 'League' THEN d.id ELSE NULL END)"
    detail_sql = "GROUP_CONCAT(DISTINCT CASE WHEN ct.name = 'League' THEN d.id ELSE NULL END)"
    flags = ['hide_person', 'hide_source', 'hide_top8']

    @property
    def description_safe(self) -> str:
        return f'Play in the <a href="{url_for("signup")}">league</a>.'

    def leaderboard_heading(self) -> str:
        return gettext('Entries')

    def localised_display(self, n: int) -> str:
        return ngettext('1 league entry', '%(num)d league entries', n)

class PerfectRun(CountedAchievement):
    key = 'perfect_runs'
    title = 'Perfect League Run'
    description_safe = 'Complete a 5–0 run in the league.'
    sql = "SUM(CASE WHEN ct.name = 'League' AND dc.wins >= 5 AND dc.losses = 0 THEN 1 ELSE 0 END)"
    detail_sql = "GROUP_CONCAT(CASE WHEN ct.name = 'League' AND dc.wins >= 5 AND dc.losses = 0 THEN d.id ELSE NULL END)"
    flags = ['hide_person', 'hide_source', 'hide_top8']

    def leaderboard_heading(self) -> str:
        return gettext('Runs')

    def localised_display(self, n: int) -> str:
        return ngettext('1 perfect run', '%(num)d perfect runs', n)

class FlawlessRun(CountedAchievement):
    key = 'flawless_runs'
    title = 'Flawless League Run'
    description_safe = 'Complete a 5–0 run in the league without losing a game.'
    sql = 'SUM(CASE WHEN d.id IN (SELECT id FROM flawless_decks1) THEN 1 ELSE 0 END)'
    detail_sql = 'GROUP_CONCAT(CASE WHEN d.id IN (SELECT id FROM flawless_decks2) THEN d.id ELSE NULL END)'
    flags = ['hide_person', 'hide_source', 'hide_top8']

    def leaderboard_heading(self) -> str:
        return gettext('Runs')

    def localised_display(self, n: int) -> str:
        return ngettext('1 flawless run', '%(num)d flawless runs', n)

    # Duplicating this query seems obviously wrong, but it doesn't work if we do the obvious thing and just reuse it
    @property
    def with_sql(self) -> str:
        return """flawless_decks1 AS
                (
                    SELECT
                        d.id AS id
                    FROM
                        deck AS d
                    INNER JOIN
                        deck_match AS dm
                    ON
                        dm.deck_id = d.id
                    INNER JOIN
                        deck_match AS odm
                    ON
                        dm.match_id = odm.match_id AND odm.deck_id <> d.id
                    WHERE
                        d.competition_id IN ({competition_ids_by_type_select})
                    GROUP BY
                        d.id
                    HAVING
                        SUM(dm.games) = 10 AND SUM(odm.games) = 0
                ),
                flawless_decks2 AS
                (
                    SELECT
                        d.id AS id
                    FROM
                        deck AS d
                    INNER JOIN
                        deck_match AS dm
                    ON
                        dm.deck_id = d.id
                    INNER JOIN
                        deck_match AS odm
                    ON
                        dm.match_id = odm.match_id AND odm.deck_id <> d.id
                    WHERE
                        d.competition_id IN ({competition_ids_by_type_select})
                    GROUP BY
                        d.id
                    HAVING
                        SUM(dm.games) = 10 AND SUM(odm.games) = 0
                )
        """.format(competition_ids_by_type_select=query.competition_ids_by_type_select('League'))

class PerfectRunCrusher(CountedAchievement):
    key = 'perfect_run_crushes'
    title = 'Perfect Run Crusher'
    description_safe = "Beat a player that's 4–0 in the league."
    def leaderboard_heading(self) -> str:
        return gettext('Crushes')
    def localised_display(self, n: int) -> str:
        return ngettext('1 perfect run crush', '%(num)d perfect run crushes', n)
    sql = 'SUM(CASE WHEN crush_records.crush_count IS NULL THEN 0 ELSE crush_records.crush_count END)'
    detail_sql = 'GROUP_CONCAT(crush_records.crushee_ids)'
    join_sql = 'LEFT JOIN crush_records ON d.id = crush_records.crusher_id'
    flags = ['hide_source', 'hide_top8']
    @property
    def with_sql(self) -> str:
        return """
            crushes AS
                (
                    SELECT
                        -- MAX here is just to fool MySQL to give us the id of the deck that crushed the perfect run from an aggregate function. There is only one value to MAX.
                        MAX(CASE WHEN dm.games < odm.games AND dm.match_id IN (SELECT MAX(match_id) FROM deck_match WHERE deck_id = d.id) THEN odm.deck_id ELSE NULL END) AS crusher_id,
                        d.id AS crushee_id
                    FROM
                        deck AS d
                    INNER JOIN
                        deck_match AS dm
                    ON
                        dm.deck_id = d.id
                    INNER JOIN
                        deck_match AS odm
                    ON
                        dm.match_id = odm.match_id AND odm.deck_id <> d.id
                    WHERE
                        d.competition_id IN ({competition_ids_by_type_select})
                    GROUP BY
                        d.id
                    HAVING
                        SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) >=4
                    AND
                        SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) = 1
                    AND
                        SUM(CASE WHEN dm.games < odm.games AND dm.match_id IN (SELECT MAX(match_id) FROM deck_match WHERE deck_id = d.id) THEN 1 ELSE 0 END) = 1
                ),
                crush_records AS (SELECT crusher_id, COUNT(crushee_id) AS crush_count, GROUP_CONCAT(crushee_id) AS crushee_ids FROM crushes GROUP BY crusher_id)
            """.format(competition_ids_by_type_select=query.competition_ids_by_type_select('League'))

class AncientGrudge(CountedAchievement):
    key = 'ancient_grudges'
    title = 'Ancient Grudge'
    description_safe = 'Beat a player in the knockout rounds of a tournament after losing to them in the knockout rounds of an earlier tournament in the same season.'
    def leaderboard_heading(self) -> str:
        return gettext('grudges repaid')
    def localised_display(self, n: int) -> str:
        return ngettext('1 grudge repaid', '%(num)d grudges repaid', n)
    sql = """COUNT(DISTINCT agdi.grudge_id)"""
    detail_sql = """GROUP_CONCAT(DISTINCT CASE WHEN agdi.id IS NOT NULL THEN agdi.both_ids ELSE NULL END)"""
    join_sql = 'LEFT JOIN ancient_grudge_deck_ids AS agdi ON d.id = agdi.id'
    flags = ['hide_source']
    @property
    def with_sql(self) -> str:
        return """knockouts AS
            (
                SELECT
                    dm1.deck_id AS winner_deck_id,
                    dm2.deck_id AS loser_deck_id,
                    p1.id AS winner_id,
                    p2.id AS loser_id,
                    season.id AS season_id,
                    `match`.date
                FROM
                    deck AS d
                LEFT JOIN
                    person AS p1
                ON
                    d.person_id = p1.id
                LEFT JOIN
                    deck_match AS dm1
                ON
                    d.id = dm1.deck_id
                LEFT JOIN
                    `match`
                ON
                    dm1.match_id = `match`.id
                LEFT JOIN
                    deck_match AS dm2
                ON
                    `match`.id = dm2.match_id AND dm2.deck_id != dm1.deck_id
                LEFT JOIN
                    deck AS d2
                ON
                    dm2.deck_id = d2.id
                LEFT JOIN
                    person AS p2
                ON
                    d2.person_id = p2.id
                {season_join}
                WHERE
                    dm1.games > dm2.games AND elimination > 0
            ),
            ancient_grudge_deck_ids AS
            (
                SELECT
                    k2.winner_deck_id AS id,
                    k1.winner_deck_id AS grudge_id,
                    CONCAT(k1.winner_deck_id, ",", k2.winner_deck_id) AS both_ids
                FROM
                    knockouts AS k1
                JOIN
                    knockouts AS k2
                ON
                    k1.season_id = k2.season_id AND k1.winner_id = k2.loser_id AND k1.loser_id = k2.winner_id AND k2.date > k1.date
            )""".format(season_join=query.season_join())

class BurningVengeance(CountedAchievement):
    key = 'burning_vengeances'
    title = 'Burning Vengeance'
    description_safe = 'Beat a player in the knockout rounds of a tournament after losing to them in the Swiss.'
    def leaderboard_heading(self) -> str:
        return gettext('defeats avenged')
    def localised_display(self, n: int) -> str:
        return ngettext('1 defeat avenged', '%(num)d defeats avenged', n)
    sql = 'COUNT(DISTINCT CASE WHEN d.id IN (SELECT id FROM burning_vengeance_decks) THEN d.id ELSE NULL END)'
    detail_sql = 'GROUP_CONCAT(bvd.both_ids)'
    join_sql = 'LEFT JOIN burning_vengeance_decks AS bvd ON d.id = bvd.id'
    with_sql = """burning_vengeance_decks AS
                (
                    SELECT
                        distinct(dm1.deck_id) AS id,
                        CONCAT(dm1.deck_id, ",", odm1.deck_id) AS both_ids
                    FROM
                        deck_match AS dm1
                    INNER JOIN
                        deck_match AS odm1
                    ON
                        odm1.match_id = dm1.match_id AND odm1.deck_id != dm1.deck_id
                    INNER JOIN
                        `match` AS m1
                    ON
                        m1.id = dm1.match_id
                    INNER JOIN
                        deck_match AS dm2
                    ON
                        dm1.deck_id = dm2.deck_id AND dm2.match_id != dm1.match_id
                    INNER JOIN
                        deck_match AS odm2
                    ON
                        odm2.match_id = dm2.match_id AND odm2.deck_id = odm1.deck_id
                    INNER JOIN
                        `match` AS m2
                    ON
                        m2.id = dm2.match_id
                    WHERE
                        dm1.games < odm1.games AND m1.elimination = 0 AND dm2.games > odm2.games AND m2.elimination > 0
                    ORDER BY
                        id
                )"""
    flags = ['hide_source']

class Deckbuilder(CountedAchievement):
    key = 'deckbuilder'
    title = 'Deck Builder'
    description_safe = 'Have someone else register an exact copy of a deck you registered first.'
    sql = 'COUNT(DISTINCT CASE WHEN d.id IN (SELECT original FROM repeats WHERE newplayer) AND d.id NOT IN (SELECT copy FROM repeats) THEN d.id ELSE NULL END)'
    detail_sql = "GROUP_CONCAT(CASE WHEN d.id IN (SELECT original FROM repeats WHERE newplayer) AND d.id NOT IN (SELECT copy FROM repeats) THEN CONCAT(d.id, ',', imitators.imitator_ids) ELSE NULL END)"
    join_sql = 'LEFT JOIN imitators ON imitators.original = d.id'
    with_sql = """
        repeats AS
            (
                SELECT
                    d1.id AS original, d2.id AS copy, d1.person_id != d2.person_id AS newplayer, d1.person_id as original_person_id
                FROM
                    deck AS d1
                JOIN
                    deck AS d2
                ON d1.decklist_hash = d2.decklist_hash AND d1.created_date < d2.created_date
            ),
        imitators AS (SELECT original, GROUP_CONCAT(copy) AS imitator_ids FROM repeats WHERE newplayer GROUP BY original)
    """

    def leaderboard_heading(self) -> str:
        return gettext('Decks')

    def localised_display(self, n: int) -> str:
        return ngettext('1 deck played by others', '%(num)d decks played by others', n)

class Pioneer(CountedAchievement):
    key = 'pioneer'
    title = 'Pioneer'
    description_safe = 'Have one of your decks recognised as the first of a new archetype.'
    sql = 'SUM(CASE WHEN d.id IN (SELECT * FROM pioneer_decks) THEN 1 ELSE 0 END)'
    detail_sql = 'GROUP_CONCAT(CASE WHEN d.id IN (SELECT * FROM pioneer_decks) THEN d.id ELSE NULL END)'
    with_sql = """
        pioneer_decks AS
        (
            SELECT
                d.id
            FROM
                deck AS d
            LEFT JOIN
                deck AS d2 ON d.archetype_id = d2.archetype_id AND d.created_date > d2.created_date
            LEFT JOIN
                archetype as a ON d.archetype_id = a.id
            WHERE
                d2.created_date IS NULL and d.archetype_id IS NOT NULL
        )"""
    flags = ['hide_person', 'show_archetype']

    def leaderboard_heading(self) -> str:
        return gettext('Archetypes')

    def localised_display(self, n: int) -> str:
        return ngettext('1 archetype pioneered', '%(num)d archetypes pioneered', n)

class VarietyPlayer(BooleanAchievement):
    key = 'variety_player'
    title = 'Variety Player'
    season_text = 'Finished five-match league runs with three or more different archetypes this season'
    description_safe = 'Finish five-match league runs with three or more different archetypes in a single season.'
    sql = 'CASE WHEN COUNT(DISTINCT CASE WHEN falr.deck_id IS NOT NULL THEN d.archetype_id ELSE NULL END) >= 3 THEN True ELSE False END'
    detail_sql = """
                    CASE WHEN
                        COUNT(DISTINCT CASE WHEN falr.deck_id IS NOT NULL THEN d.archetype_id ELSE NULL END) >= 3
                    THEN
                        GROUP_CONCAT(falr.deck_id)
                    ELSE
                        NULL
                    END
                """
    with_sql = """
                    first_arch_league_runs AS
                    (
                        SELECT
                            MIN(d.id) as deck_id,
                            d.person_id AS person_id,
                            season.id AS season_id,
                            d.archetype_id AS archetype_id
                        FROM
                            deck AS d
                        LEFT JOIN
                            deck_cache AS dc ON dc.deck_id = d.id
                        {season_join}
                        {competition_join}
                        WHERE
                            ct.name = 'League' AND dc.wins + dc.losses >= 5
                        GROUP BY
                            person_id,
                            season_id,
                            archetype_id
                    )""".format(season_join=query.season_join(), competition_join=query.competition_join())
    join_sql = 'LEFT JOIN first_arch_league_runs AS falr ON d.id = falr.deck_id'
    flags = ['hide_person', 'hide_source', 'hide_top8', 'show_archetype']

    @staticmethod
    def alltime_text(n: int) -> str:
        what = ngettext('1 season', '%(num)d different seasons', n)
        return f'Finished five-match league runs with three or more different archetypes in {what}'

class Specialist(BooleanAchievement):
    key = 'specialist'
    title = 'Specialist'
    season_text = 'Reached the elimination rounds of a tournament playing the same archetype three or more times this season'
    description_safe = 'Reach the elimination rounds of a tournament playing the same archetype three or more times in a single season.'
    sql = 'CASE WHEN EXISTS (SELECT * FROM arch_top_n_count1 AS atnc WHERE p.id = atnc.person_id AND season.id = atnc.season_id AND n >= 3) THEN TRUE ELSE FALSE END'
    detail_sql = "GROUP_CONCAT(CASE WHEN d.finish <= c.top_n AND ct.name = 'Gatherling' AND d.archetype_id IN (SELECT archetype_id FROM arch_top_n_count2 AS atnc WHERE p.id = atnc.person_id AND season.id = atnc.season_id AND n >= 3) THEN d.id ELSE NULL END)"
    with_sql = """
                top_ns AS
                    (
                        SELECT
                            d.id as deck_id,
                            p.id AS person_id,
                            season.id AS season_id,
                            d.archetype_id AS archetype_id
                        FROM
                            person AS p
                        LEFT JOIN
                            deck AS d
                        ON
                            d.person_id = p.id
                        {season_join}
                        {competition_join}
                        WHERE
                            d.finish <= c.top_n AND ct.name = 'Gatherling'
                    ),
                arch_top_n_count1 AS
                    (
                        SELECT person_id, season_id, archetype_id, COUNT(DISTINCT deck_id) AS n FROM top_ns GROUP BY person_id, season_id, archetype_id
                    ),
                arch_top_n_count2 AS
                    (
                        SELECT person_id, season_id, archetype_id, COUNT(DISTINCT deck_id) AS n FROM top_ns GROUP BY person_id, season_id, archetype_id
                    )
                """.format(season_join=query.season_join(), competition_join=query.competition_join())
    flags = ['hide_person', 'hide_source', 'show_archetype']
    @staticmethod
    def alltime_text(n: int) -> str:
        what = ngettext('1 season', '%(num)d different seasons', n)
        return f'Reached the elimination rounds of a tournament playing the same archetype three or more times in {what}'

class Generalist(BooleanAchievement):
    key = 'generalist'
    title = 'Generalist'
    season_text = 'Reached the elimination rounds of a tournament playing three or more different archetypes this season'
    description_safe = 'Reach the elimination rounds of a tournament playing three or more different archetypes in a single season.'
    sql = "CASE WHEN COUNT(DISTINCT CASE WHEN d.finish <= c.top_n AND ct.name = 'Gatherling' THEN d.archetype_id ELSE NULL END) >= 3 THEN True ELSE False END"
    detail_sql = """
                    CASE WHEN
                        COUNT(DISTINCT CASE WHEN d.finish <= c.top_n AND ct.name = 'Gatherling' THEN d.archetype_id ELSE NULL END) >= 3
                    THEN
                        GROUP_CONCAT(DISTINCT CASE WHEN d.id IN (SELECT deck_id FROM first_arch_top_ns) THEN d.id ELSE NULL END)
                    ELSE
                        NULL
                    END"""
    with_sql = 'first_arch_top_ns AS (SELECT MIN(deck_id) AS deck_id, person_id, season_id FROM top_ns GROUP BY person_id, season_id, archetype_id)'
    flags = ['hide_person', 'hide_source', 'show_archetype']
    @staticmethod
    def alltime_text(n: int) -> str:
        what = ngettext('1 season', '%(num)d different seasons', n)
        return f'Reached the elimination rounds of a tournament playing three or more different archetypes in {what}'

class Completionist(BooleanAchievement):
    key = 'completionist'
    title = 'Completionist'
    season_text = 'Has not retired a league run this season'
    description_safe = 'Play the whole season without retiring an unfinished league run.'
    sql = "CASE WHEN COUNT(CASE WHEN ct.name = 'League' THEN 1 ELSE NULL END) > 0 AND COUNT(CASE WHEN d.retired = 1 THEN 1 ELSE NULL END) = 0 THEN True ELSE False END"

    @staticmethod
    def alltime_text(n: int) -> str:
        what = ngettext('1 season', '%(num)d different seasons', n)
        return f'Played in {what} without retiring a league run'
