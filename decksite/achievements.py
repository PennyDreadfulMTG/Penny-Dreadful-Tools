from typing import Dict, List, Optional

from flask_babel import ngettext

from decksite.data import query
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

def displayed_achievements(person: 'person.Person') -> List[Dict[str, str]]:
    result = []
    if person.name in [host for series in tournaments.all_series_info() for host in series['hosts']]:
        result.append({'name': 'Tournament Organizer', 'detail': 'Run a tournament for the Penny Dreadful community'})
    achievements = person.get('achievements', {})
    for k, t, v1, vp in ACHIEVEMENTS_TEXT:
        if k in achievements and achievements[k] > 0:
            result.append({'name':t, 'detail':ngettext(f'1 {v1}', f'%(num)d {vp}', person.achievements[k])})
    if achievements.get('completionist', 0) > 0:
        result.append({'name':'Completionist', 'detail':'Never retired a league run'})
    return result
