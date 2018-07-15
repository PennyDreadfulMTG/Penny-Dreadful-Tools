from flask import url_for
from sqlalchemy import func

from logsite.view import View
from shared import redis

from .. import APP, db
from ..data import match


@APP.route('/people/')
def people():
    view = People()
    return view.page()

# pylint: disable=no-self-use
class People(View):
    def __init__(self) -> None:
        people_query = db.User.query.order_by(db.User.name.asc()).paginate()
        self.people = people_query.items
        self.has_next = people_query.has_next
        self.has_prev = people_query.has_prev
        if people_query.has_next:
            self.next_url = url_for('people', page=people_query.next_num)
        if people_query.has_prev:
            self.prev_url = url_for('people', page=people_query.prev_num)

    def prepare(self):
        for p in self.people:
            key = f'logsite:people:{p.id}'
            data = redis.get_container(key, ex=3600)
            if data:
                p.fav_format = data.fav_format
                p.num_matches = data.num_matches
            else:
                p.num_matches = match.get_recent_matches_by_player(p.name).count()
                p.formats = db.DB.session.query(match.Match, func.count(match.Match.format_id)).filter(match.Match.players.any(db.User.id == p.id)).group_by(match.Match.format_id).order_by(func.count(match.Match.format_id).desc()).all()
                if p.formats:
                    p.fav_format = '{0} ({1} matches)'.format(p.formats[0][0].format.get_name(), p.formats[0][1])
                else:
                    p.fav_format = '⸺'
                redis.store(key, {'fav_format': p.fav_format, 'num_matches': p.num_matches}, ex=3600)
