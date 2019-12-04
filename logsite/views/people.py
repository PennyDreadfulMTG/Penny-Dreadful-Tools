from flask import url_for

from logsite.view import View
from shared_web.decorators import fill_args
from shared import redis

from .. import APP, db
from ..data import match


@APP.route('/people/')
def people() -> str:
    view = People()
    return view.page()

# pylint: disable=no-self-use
class People(View):
    @fill_args('page')
    def __init__(self, page: str = '1') -> None:
        pagenum = int(page)
        people_query = db.User.select().order_by(db.User.name.asc()).paginate(pagenum, 20)
        self.people = people_query
        self.has_next = True if people_query else False
        self.has_prev = pagenum > 1
        self.has_pagination = self.has_next or self.has_prev
        if self.has_next:
            self.next_url = url_for('.people', page=pagenum + 1)
        if self.has_prev:
            self.prev_url = url_for('.people', page=pagenum - 1)

    def prepare(self) -> None:
        for p in self.people:
            key = f'logsite:people:{p.id}'
            data = redis.get_container(key, ex=3600)
            if data:
                p.fav_format = data.fav_format
                p.num_matches = data.num_matches
            else:
                p.num_matches = match.get_recent_matches_by_player(p.name).count()
                stmt = """
                    SELECT f.name, COUNT(*) AS num_matches
                    FROM matchplayers AS mp
                    INNER JOIN `match` AS m ON mp.match_id = m.id
                    INNER JOIN format AS f ON m.format_id = f.id
                    WHERE mp.user_id = %s
                    GROUP BY f.id;
                """
                p.formats = db.DB.execute_sql(stmt, [p.id]).fetchall()
                if p.formats:
                    p.fav_format = '{0} ({1} matches)'.format(p.formats[0][0], p.formats[0][1])
                else:
                    p.fav_format = '⸺'
                redis.store(key, {'fav_format': p.fav_format, 'num_matches': p.num_matches}, ex=3600)
