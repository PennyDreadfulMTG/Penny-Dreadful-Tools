import re
from typing import TYPE_CHECKING, Dict, List, Optional

from flask import url_for
from flask_babel import ngettext

import decksite
from decksite.data import query
from decksite.database import db
from magic import tournaments
from shared.container import Container
from shared.decorators import retry_after_calling

if TYPE_CHECKING:
    from decksite.data import person # pylint:disable=unused-import

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
    create_columns = ', '.join(f'`{a.key}` INT NOT NULL' for a in Achievement.all_achievements if a.in_db)
    select_columns = ', '.join(f'{a.sql} as `{a.key}`' for a in Achievement.all_achievements if a.in_db)
    return """
        CREATE TABLE IF NOT EXISTS _new_achievements (
            person_id INT NOT NULL,
            season_id INT NOT NULL,
            {cc},
            PRIMARY KEY (season_id, person_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
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
        GROUP BY
            p.id,
            season.id
        HAVING
            season.id IS NOT NULL
    """.format(cc=create_columns, sc=select_columns, season_join=query.season_join(), competition_join=query.competition_join())

def displayed_achievements(p: 'person.Person') -> List[Dict[str, str]]:
    return [d for d in (a.display(p) for a in Achievement.all_achievements) if d is not None]

# Abstract achievement classes

class Achievement:
    all_achievements: List['Achievement'] = []
    key: Optional[str] = None
    sql: Optional[str] = None
    in_db = True
    title = ''
    description_safe = ''
    def __init_subclass__(cls):
        if cls.key is not None:
            # in case anyone ever makes a poor sportsmanship achievement called DROP TABLE
            cls.key = re.sub('[^A-Za-z0-9_]+', '', cls.key)
            if cls.key in [c.key for c in cls.all_achievements]:
                print(f"Warning: Two achievements have the same normalised key {cls.key}. This won't do any permanent damage to the database but the results are almost certainly not as intended.")
            cls.all_achievements.append(cls())
    def display(self, _: 'person.Person') -> Optional[Dict[str, str]]: # pylint: disable=no-self-use
        return None
    def load_summary(self) -> Optional[str]: # pylint: disable=no-self-use
        return None

class CountedAchievement(Achievement):
    singular = ''
    plural = ''
    def display(self, p) -> Optional[Dict[str, str]]:
        n = p.get('achievements', {}).get(self.key, 0)
        if n > 0:
            return {'name': self.title, 'detail': ngettext(f'1 {self.singular}', f'%(num)d {self.plural}', n)}
        return None
    @retry_after_calling(preaggregate_achievements)
    def load_summary(self) -> Optional[str]:
        sql = f"""SELECT SUM(`{self.key}`) AS num, SUM(CASE WHEN `{self.key}` > 0 THEN 1 ELSE 0 END) AS pnum FROM _achievements"""
        for r in db().select(sql):
            res = Container(r)
            return f'Earned {res.num} times by {res.pnum} players.'
        return None

class BooleanAchievement(Achievement):
    season_text = ''
    @staticmethod
    def alltime_text(_: int) -> str:
        return ''
    def display(self, p: 'person.Person') -> Optional[Dict[str, str]]:
        n = p.get('achievements', {}).get(self.key, 0)
        if n > 0:
            if decksite.get_season_id() == 'all':
                return {'name': self.title, 'detail': self.alltime_text(n)}
            return {'name': self.title, 'detail': self.season_text}
        return None
    @retry_after_calling(preaggregate_achievements)
    def load_summary(self) -> Optional[str]:
        sql = f"""SELECT SUM(s) AS num, COUNT(s) AS pnum FROM
                    (SELECT SUM(`{self.key}`) AS s FROM _achievements WHERE `{self.key}` > 0 GROUP BY person_id)
                    AS _"""
        for r in db().select(sql):
            res = Container(r)
            return f'Earned {res.num} times by {res.pnum} players.'
        return None

# Actual achievement definitions

class TournamentOrganizer(Achievement):
    key = 'tournament_organizer'
    in_db = False
    title = 'Tournament Organizer'
    description_safe = 'Run a tournament for the Penny Dreadful community.'
    def __init__(self):
        self.hosts = [host for series in tournaments.all_series_info() for host in series['hosts']]
    def display(self, p: 'person.Person') -> Optional[Dict[str, str]]:
        if p.name in self.hosts:
            return {'name': 'Tournament Organizer', 'detail': 'Ran a tournament for the Penny Dreadful community'}
        return None
    def load_summary(self) -> Optional[str]:
        return f'Earned by {len(self.hosts)} players.'

class TournamentPlayer(CountedAchievement):
    key = 'tournament_entries'
    title = 'Tournament Player'
    singular = 'tournament entered'
    plural = 'tournaments entered'
    @property
    def description_safe(self):
        return 'Play in an official Penny Dreadful tournament on <a href="https://gatherling.com/">gatherling.com</a>'
    sql = "COUNT(DISTINCT CASE WHEN ct.name = 'Gatherling' THEN d.id ELSE NULL END)"

class TournamentWinner(CountedAchievement):
    key = 'tournament_wins'
    title = 'Tournament Winner'
    singular = 'victory'
    plural = 'victories'
    description_safe = 'Win a tournament.'
    sql = "COUNT(DISTINCT CASE WHEN d.finish = 1 AND ct.name = 'Gatherling' THEN d.id ELSE NULL END)"

class LeaguePlayer(CountedAchievement):
    key = 'league_entries'
    title = 'League Player'
    singular = 'league entry'
    plural = 'league entries'
    @property
    def description_safe(self):
        return f'Play in the <a href="{url_for("signup")}">league</a>.'
    sql = "COUNT(DISTINCT CASE WHEN ct.name = 'League' THEN d.id ELSE NULL END)"

class PerfectRun(CountedAchievement):
    key = 'perfect_runs'
    title = 'Perfect League Run'
    singular = 'perfect run'
    plural = 'perfect runs'
    description_safe = 'Complete a 5–0 run in the league.'
    sql = "SUM(CASE WHEN ct.name = 'League' AND dc.wins >= 5 AND dc.losses = 0 THEN 1 ELSE 0 END)"

class FlawlessRun(CountedAchievement):
    key = 'flawless_runs'
    title = 'Flawless League Run'
    singular = 'flawless run'
    plural = 'flawless runs'
    description_safe = 'Complete a 5–0 run in the league without losing a game.'
    @property
    def sql(self):
        return """SUM(CASE WHEN ct.name = 'League' AND d.id IN
                    (
                        SELECT
                            d.id
                        FROM
                            deck as d
                        INNER JOIN
                            deck_match as dm
                        ON
                            dm.deck_id = d.id
                        INNER JOIN
                            deck_match as odm
                        ON
                            dm.match_id = odm.match_id and odm.deck_id <> d.id
                        WHERE
                            d.competition_id IN ({competition_ids_by_type_select})
                        GROUP BY
                            d.id
                        HAVING
                            SUM(dm.games) = 10 and sum(odm.games) = 0
                    )
                THEN 1 ELSE 0 END)""".format(competition_ids_by_type_select=query.competition_ids_by_type_select('League'))

class PerfectRunCrusher(CountedAchievement):
    key = 'perfect_run_crushes'
    title = 'Perfect Run Crusher'
    singular = 'dream in tatters'
    plural = 'dreams in tatters'
    description_safe = "Beat a player that's 4–0 in the league."
    @property
    def sql(self):
        return """SUM(CASE WHEN d.id IN
                    (
                        SELECT
                            -- MAX here is just to fool MySQL to give us the id of the deck that crushed the perfect run from an aggregate function. There is only one value to MAX.
                            MAX(CASE WHEN dm.games < odm.games AND dm.match_id IN (SELECT MAX(match_id) FROM deck_match WHERE deck_id = d.id) THEN odm.deck_id ELSE NULL END) AS deck_id
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
                    )
                THEN 1 ELSE 0 END)""".format(competition_ids_by_type_select=query.competition_ids_by_type_select('League'))

class Pioneer(CountedAchievement):
    key = 'pioneer'
    title = 'Pioneer'
    singular = 'archetype pioneered'
    plural = 'archetypes pioneered'
    description_safe = 'Have one of your decks recognised as the first of a new archetype.'
    sql = """SUM(CASE WHEN d.id in
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
                )
            THEN 1 ELSE 0 END)"""

class Specialist(BooleanAchievement):
    key = 'specialist'
    title = 'Specialist'
    season_text = 'Reached the elimination rounds of a tournament playing the same archetypes three times this season'
    @staticmethod
    def alltime_text(n):
        what = ngettext('1 season', f'{n} different seasons', n)
        return f'Reached the elimination rounds of a tournament playing the same archetype three times in {what}'
    description_safe = 'Reach the elimination rounds of a tournament playing the same archetype three times in a single season.'
    sql = """CASE WHEN EXISTS
                (
                    SELECT
                        p.id
                    FROM
                        (
                            SELECT p.id AS inner_pid, season.id AS inner_seasonid, COUNT(d.id) AS archcount
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
                            GROUP BY
                                p.id,
                                season.id,
                                d.archetype_id
                            HAVING archcount >= 3
                        ) AS spec_archs
                    WHERE
                        p.id = inner_pid AND season.id = inner_seasonid
                )
            THEN True ELSE False END""".format(season_join=query.season_join(), competition_join=query.competition_join())

class Generalist(BooleanAchievement):
    key = 'generalist'
    title = 'Generalist'
    season_text = 'Reached the elimination rounds of a tournament playing three different archetypes this season'
    @staticmethod
    def alltime_text(n):
        what = ngettext('1 season', f'{n} different seasons', n)
        return f'Reached the elimination rounds of a tournament playing three different archetypes in {what}'
    description_safe = 'Reach the elimination rounds of a tournament playing three different archetypes in a single season.'
    sql = "CASE WHEN COUNT(DISTINCT CASE WHEN d.finish <= c.top_n AND ct.name = 'Gatherling' THEN d.archetype_id ELSE NULL END) >= 3 THEN True ELSE False END"

class Completionist(BooleanAchievement):
    key = 'completionist'
    title = 'Completionist'
    season_text = 'Never retired a league run this season'
    @staticmethod
    def alltime_text(n):
        what = ngettext('1 season', f'{n} different seasons', n)
        return f'Played in {what} without retiring a league run'
    description_safe = 'Play the whole season without retiring an unfinished league run.'
    sql = 'CASE WHEN COUNT(CASE WHEN d.retired = 1 THEN 1 ELSE NULL END) = 0 THEN True ELSE False END'
