from flask import url_for
from sqlalchemy import func

from logsite.view import View

from .. import APP, db
from ..data import match


@APP.route('/people/')
def people():
    view = People()
    return view.page()

# pylint: disable=no-self-use
class People(View):
    def __init__(self):
        people_query = db.User.query.order_by(db.User.name.asc()).paginate(per_page=50)
        self.people = people_query.items
        self.has_next = people_query.has_next
        self.has_prev = people_query.has_prev
        if people_query.has_next:
            self.next_url = url_for('people', page=people_query.next_num)
        if people_query.has_prev:
            self.prev_url = url_for('people', page=people_query.prev_num)

    def subtitle(self):
        return None

    def prepare(self):
        for p in self.people:
            p.num_matches = match.get_recent_matches_by_player(p.name).count()
            p.formats = db.db.session.query(match.Match, func.count(match.Match.format_id)).filter(match.Match.players.any(db.User.id == p.id)).group_by(match.Match.format_id).order_by(func.count(match.Match.format_id).desc()).all()
            if p.formats:
                p.fav_format = '{0} ({1} matches)'.format(p.formats[0][0].format.get_name(), p.formats[0][1])
            else:
                p.fav_format = '⸺'
