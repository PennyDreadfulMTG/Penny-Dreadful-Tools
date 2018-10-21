from typing import Dict, List, Optional

from flask import url_for
from flask_babel import ngettext

from decksite.data import person, query  # pylint:disable=unused-import
from magic import tournaments

ACHIEVEMENTS_TEXT = [
    ('tournament_wins', 'Tournament Winner', 'Win', 'Wins'),
    ('tournament_entries', 'Tournament Player', 'Entry', 'Entries'),
    ('perfect_runs', 'Perfect League Run', 'Perfect Run', 'Perfect Runs'),
    ('flawless_runs', 'Flawless League Run', 'Flawless Run', 'Flawless Runs'),
    ('league_entries', 'League Player', 'Entry', 'Entries'),
    ('perfect_run_crushes', 'Perfect Run Crusher', 'Crush', 'Crushes')
]

def load_query(people_by_id: Dict[int, 'person.Person'], season_id: Optional[int]) -> str:
    return """
        SELECT
            person_id AS id,
            SUM(tournament_entries) AS tournament_entries,
            SUM(tournament_wins) AS tournament_wins,
            SUM(league_entries) AS league_entries,
            SUM(completionist) AS completionist,
            SUM(perfect_runs) AS perfect_runs,
            SUM(flawless_runs) AS flawless_runs,
            SUM(perfect_run_crushes) AS perfect_run_crushes
        FROM
            _achievements AS a
        WHERE
            person_id IN ({ids}) AND ({season_query})
        GROUP BY
            person_id
    """.format(ids=', '.join(str(k) for k in people_by_id.keys()), season_query=query.season_query(season_id))

def preaggregate_query() -> str:
    return """
        CREATE TABLE IF NOT EXISTS _new_achievements (
            person_id INT NOT NULL,
            season_id INT NOT NULL,
            tournament_entries INT NOT NULL,
            tournament_wins INT NOT NULL,
            league_entries INT NOT NULL,
            completionist BOOLEAN NOT NULL,
            perfect_runs INT NOT NULL,
            flawless_runs INT NOT NULL,
            perfect_run_crushes INT NOT NULL,
            PRIMARY KEY (season_id, person_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            p.id AS person_id,
            season.id AS season_id,
            COUNT(DISTINCT CASE WHEN ct.name = 'Gatherling' THEN d.id ELSE NULL END) AS tournament_entries,
            COUNT(DISTINCT CASE WHEN d.finish = 1 AND ct.name = 'Gatherling' THEN d.id ELSE NULL END) AS tournament_wins,
            COUNT(DISTINCT CASE WHEN ct.name = 'League' THEN d.id ELSE NULL END) AS league_entries,
            CASE WHEN COUNT(CASE WHEN d.retired = 1 THEN 1 ELSE NULL END) = 0 THEN True ELSE False END AS completionist,
            SUM(CASE WHEN ct.name = 'League' AND dc.wins >= 5 AND dc.losses = 0 THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(
                CASE WHEN ct.name = 'League' AND d.id IN
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
                THEN 1 ELSE 0 END
            ) AS flawless_runs,
            SUM(
                CASE WHEN d.id IN
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
                THEN 1 ELSE 0 END
            ) AS perfect_run_crushes
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
    """.format(competition_ids_by_type_select=query.competition_ids_by_type_select('League'), season_join=query.season_join(), competition_join=query.competition_join())

def descriptions() -> List[Dict[str, str]]:
    return [{'title': 'Tournament Organizer',
             'description_safe': 'Run a tournament for the Penny Dreadful community.'},
            {'title': 'Tournament Player',
             'description_safe': 'Play in an official Penny Dreadful tournament on <a href="https://gatherling.com/">gatherling.com</a>'},
            {'title': 'Tournament Winner',
             'description_safe': 'Win a tournament.'},
            {'title': 'League Player',
             'description_safe': f'Play in the <a href="{url_for("signup")}">league</a>.'},
            {'title': 'Perfect League Run',
             'description_safe': 'Complete a 5–0 run in the league.'},
            {'title': 'Flawless League Run',
             'description_safe': 'Complete a 5–0 run in the league without losing a game.'},
            {'title': 'Perfect Run Crusher',
             'description_safe': "Beat a player that's 4–0 in the league."},
            {'title': 'Completionist',
             'description_safe': 'Go the whole season without retiring an unfinished league run.'},
            ]

def displayed_achievements(p: 'person.Person') -> List[Dict[str, str]]:
    result = []
    if p.name in [host for series in tournaments.all_series_info() for host in series['hosts']]:
        result.append({'name': 'Tournament Organizer', 'detail': 'Run a tournament for the Penny Dreadful community'})
    achievements = p.get('achievements', {})
    for k, t, v1, vp in ACHIEVEMENTS_TEXT:
        if k in achievements and achievements[k] > 0:
            result.append({'name':t, 'detail':ngettext(f'1 {v1}', f'%(num)d {vp}', p.achievements[k])})
    if achievements.get('completionist', 0) > 0:
        result.append({'name':'Completionist', 'detail':'Never retired a league run'})
    return result
