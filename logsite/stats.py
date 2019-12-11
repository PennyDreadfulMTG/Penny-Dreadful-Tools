import datetime
from typing import Any, Dict, List

from flask import Response

from shared import dtutil

from . import APP, db
from .api import return_json
from .data import match


@APP.route('/stats.json')
def stats() -> Response:
    val: Dict[str, Any] = {}
    last_switcheroo = calc_last_switcheroo()
    if last_switcheroo:
        val['last_switcheroo'] = dtutil.dt2ts(last_switcheroo.start_time_aware())

    val['formats'] = {}
    stmt = """
    SELECT f.id,
		   f.name,
		   COUNT(*) as num_matches,
		   (SELECT COUNT(*) FROM `match` WHERE `match`.format_id = f.id AND `match`.start_time > DATE_SUB(NOW(), INTERVAL 7 DAY)) as last_week,
		   (SELECT COUNT(*) FROM `match` WHERE `match`.format_id = f.id AND `match`.start_time > DATE_SUB(NOW(), INTERVAL 14 DAY) AND `match`.start_time < DATE_SUB(NOW(), INTERVAL 7 DAY)) as last_last_week,
           (SELECT COUNT(*) FROM `match` WHERE `match`.format_id = f.id AND `match`.start_time > DATE_SUB(NOW(), INTERVAL 30 DAY)) as last_month
    FROM format as f
    INNER JOIN `match` on f.id = `match`.format_id
	 GROUP BY f.id
    ORDER BY num_matches DESC
    """
    base_query = db.DB.execute_sql(stmt, [])
    for m in base_query:
        (format_id, format_name, num_matches, last_week, last_last_week, last_month) = m
        val['formats'][format_name] = {}
        val['formats'][format_name]['id'] = format_id
        val['formats'][format_name]['name'] = format_name
        val['formats'][format_name]['num_matches'] = num_matches
        if last_week > 0:
            val['formats'][format_name]['last_week'] = {}
            val['formats'][format_name]['last_week']['num_matches'] = last_week
        if last_last_week > 0:
            val['formats'][format_name]['last_last_week'] = {}
            val['formats'][format_name]['last_last_week']['num_matches'] = last_last_week
        if last_month > 0:
            val['formats'][format_name]['last_month'] = {}
            val['formats'][format_name]['last_month']['num_matches'] = last_month

    for format_name, f in val['formats'].items():
        format_id = val['formats'][format_name]['id']
        if 'last_week' in f:
            interval = '`match`.start_time > DATE_SUB(NOW(), INTERVAL 7 DAY)'
            names = get_format_players_for_interval(interval, format_id)
            val['formats'][format_name]['last_week']['recent_players'] = names
        if 'last_last_week' in f:
            interval = '`match`.start_time > DATE_SUB(NOW(), INTERVAL 14 DAY) AND `match`.start_time < DATE_SUB(NOW(), INTERVAL 7 DAY)'
            names = get_format_players_for_interval(interval, format_id)
            val['formats'][format_name]['last_last_week']['recent_players'] = names
        if 'last_month' in f:
            interval = '`match`.start_time > DATE_SUB(NOW(), INTERVAL 30 DAY)'
            names = get_format_players_for_interval(interval, format_id)
            val['formats'][format_name]['last_month']['recent_players'] = names
        del val['formats'][format_name]['id']
    return return_json(val)

def get_format_players_for_interval(interval: str, format_id: int) -> List[str]:
    stmt = """
        SELECT b.name
        FROM user AS b
        INNER JOIN (
            SELECT user.id
            FROM user
            LEFT JOIN matchplayers ON matchplayers.user_id = user.id
            LEFT JOIN `match` ON `match`.id = matchplayers.match_id
            WHERE `match`.format_id = %s AND
            {interval}
            GROUP BY user.id
        ) AS a ON a.id = b.id
    """.format(interval=interval)
    names = db.DB.execute_sql(stmt, [format_id])
    return [n[0] for n in names]

def calc_last_switcheroo() -> match.Match:
    return match.Match.select().where(match.Match.has_unexpected_third_game).order_by(match.Match.id.desc()).first()

@APP.route('/recent.json')
def recent_json() -> Response:
    last_week = dtutil.dt2ts(dtutil.now() - datetime.timedelta(days=7))
    val: Dict[str, Any] = {}
    val['formats'] = {}
    last_f: Dict[str, int] = {}

    for m in match.Match.select().where(match.Match.start_time.to_timestamp() > last_week): # pylint: disable=no-member
        f = m.format_id
        if val['formats'].get(f.name, None) is None:
            val['formats'][f.name] = {}
        time = dtutil.dt2ts(m.start_time_aware().replace(microsecond=0, second=0, minute=0))
        last = last_f.get(f.name, None)
        if last is not None:
            while last < time:
                last = last + 3600
                val['formats'][f.name][last] = val['formats'][f.name].get(last, 0)
        else:
            last = time
        last_f[f.name] = last
        val['formats'][f.name][time] = val['formats'][f.name].get(time, 0) + 1

    return return_json(val)
