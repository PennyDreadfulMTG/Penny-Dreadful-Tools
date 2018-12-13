from typing import Any, Dict

from sqlalchemy import func, text
from flask import Response

from shared import dtutil

from . import APP, db
from .api import return_json
from .data import match
from .db import Format


@APP.route('/stats.json')
def stats() -> Response:
    val: Dict[str, Any] = {}
    last_switcheroo = calc_last_switcheroo()
    if last_switcheroo:
        val['last_switcheroo'] = dtutil.dt2ts(last_switcheroo.start_time_aware())

    val['formats'] = {}
    base_query = db.DB.session.query(match.Match.format_id, Format.name, func.count(match.Match.format_id)).join(match.Match.format).group_by(match.Match.format_id)
    for m in base_query.order_by(func.count(match.Match.format_id).desc()).all():
        (format_id, format_name, num_matches) = m
        val['formats'][format_name] = {}
        val['formats'][format_name]['name'] = format_name
        val['formats'][format_name]['num_matches'] = num_matches
    last_week = dtutil.now() - dtutil.ts2dt(7 * 24 * 60 * 60)
    for m in base_query.filter(match.Match.start_time > last_week).order_by(func.count(match.Match.format_id).desc()).all():
        (format_id, format_name, num_matches) = m
        val['formats'][format_name]['last_week'] = {}
        val['formats'][format_name]['last_week']['num_matches'] = num_matches
        stmt = text("""
            SELECT b.*
            FROM user AS b
            INNER JOIN (
                SELECT user.id
                FROM user
                LEFT JOIN match_players ON match_players.user_id = user.id
                LEFT JOIN `match` ON `match`.id = match_players.match_id
                WHERE `match`.format_id = :fid
                    AND `match`.start_time IS NOT NULL
                    AND `match`.start_time > DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY user.id
            ) AS a ON a.id = b.id
        """)
        players = db.DB.session.query(db.User).from_statement(stmt).params(fid=format_id).all()
        val['formats'][format_name]['last_week']['recent_players'] = [p.name for p in players]
    last_last_week = dtutil.now() - dtutil.ts2dt(2 * 7 * 24 * 60 * 60)
    for m in base_query.filter(match.Match.start_time < last_week).filter(match.Match.start_time > last_last_week).order_by(func.count(match.Match.format_id).desc()).all():
        (format_id, format_name, num_matches) = m
        val['formats'][format_name]['last_last_week'] = {}
        val['formats'][format_name]['last_last_week']['num_matches'] = num_matches
        stmt = text("""
            SELECT b.*
            FROM user AS b
            INNER JOIN (
                SELECT user.id
                FROM user
                LEFT JOIN match_players ON match_players.user_id = user.id
                LEFT JOIN `match` ON `match`.id = match_players.match_id
                WHERE `match`.format_id = :fid
                    AND `match`.start_time IS NOT NULL
                    AND `match`.start_time > DATE_SUB(NOW(), INTERVAL 14 DAY)
                    AND `match`.start_time < DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY user.id
            ) AS a ON a.id = b.id
        """)
        players = db.DB.session.query(db.User).from_statement(stmt).params(fid=format_id).all()
        val['formats'][format_name]['last_last_week']['recent_players'] = [p.name for p in players]

    last_month = dtutil.now() - dtutil.ts2dt(30 * 24 * 60 * 60)
    for m in base_query.filter(match.Match.start_time > last_month).order_by(func.count(match.Match.format_id).desc()).all():
        (format_id, format_name, num_matches) = m
        val['formats'][format_name]['last_month'] = {}
        val['formats'][format_name]['last_month']['num_matches'] = num_matches
        stmt = text("""
            SELECT b.*
            FROM user AS b
            INNER JOIN (
                SELECT user.id
                FROM user
                LEFT JOIN match_players ON match_players.user_id = user.id
                LEFT JOIN `match` ON `match`.id = match_players.match_id
                WHERE `match`.format_id = :fid
                    AND `match`.start_time IS NOT NULL
                    AND `match`.start_time > DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY user.id
            ) AS a ON a.id = b.id
        """)
        players = db.DB.session.query(db.User).from_statement(stmt).params(fid=format_id).all()
        val['formats'][format_name]['last_month']['recent_players'] = [p.name for p in players]
    return return_json(val)

def calc_last_switcheroo() -> match.Match:
    return match.Match.query.filter(match.Match.has_unexpected_third_game).order_by(match.Match.id.desc()).first()

@APP.route('/recent.json')
def recent_json() -> Response:
    last_week = dtutil.now() - dtutil.ts2dt(7 * 24 * 60 * 60)
    val: Dict[str, Any] = {}
    val['formats'] = {}
    last_f: Dict[str, int] = {}
    for m in match.Match.query.filter(match.Match.start_time > last_week).all():
        f = m.format
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
