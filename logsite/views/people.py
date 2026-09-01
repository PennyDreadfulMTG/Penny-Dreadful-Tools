# type ignore

from flask import url_for
from sqlalchemy import bindparam, text

from logsite.view import View
from shared import redis_wrapper as redis

from .. import APP, db


@APP.route('/people/')
def people() -> str:
    view = People()
    return view.page()

class People(View):
    def __init__(self) -> None:
        super().__init__()
        people_query = db.User.query.order_by(db.User.name.asc()).paginate()
        self.people = people_query.items
        self.has_next = people_query.has_next
        self.has_prev = people_query.has_prev
        self.has_pagination = self.has_next or self.has_prev
        if people_query.has_next:
            self.next_url = url_for('.people', page=people_query.next_num)
        if people_query.has_prev:
            self.prev_url = url_for('.people', page=people_query.prev_num)

    def prepare(self) -> None:
        uncached = []
        for p in self.people:
            key = f'logsite:people:{p.id}'
            data = redis.get_container(key, ex=3600)
            if data:
                p.fav_format = data.fav_format
                p.num_matches = data.num_matches
            else:
                uncached.append(p)

        if not uncached:
            return

        user_ids = [p.id for p in uncached]

        count_stmt = text("""
            SELECT mp.user_id, COUNT(*) AS num_matches
            FROM match_players AS mp
            WHERE mp.user_id IN :user_ids
            GROUP BY mp.user_id
        """).bindparams(bindparam('user_ids', expanding=True))
        counts = {row[0]: row[1] for row in db.DB.session.execute(count_stmt, {'user_ids': user_ids})}

        format_stmt = text("""
            SELECT mp.user_id, f.name, COUNT(*) AS num_matches
            FROM match_players AS mp
            INNER JOIN `match` AS m ON mp.match_id = m.id
            INNER JOIN format AS f ON m.format_id = f.id
            WHERE mp.user_id IN :user_ids
            GROUP BY mp.user_id, f.id
            ORDER BY mp.user_id, COUNT(*) DESC
        """).bindparams(bindparam('user_ids', expanding=True))
        formats: dict[int, str] = {}
        for row in db.DB.session.execute(format_stmt, {'user_ids': user_ids}):
            uid, fname, fcount = row[0], row[1], row[2]
            if uid not in formats:
                formats[uid] = f'{fname} ({fcount} matches)'

        for p in uncached:
            p.num_matches = counts.get(p.id, 0)
            p.fav_format = formats.get(p.id, '⸺')
            redis.store(f'logsite:people:{p.id}', {'fav_format': p.fav_format, 'num_matches': p.num_matches}, ex=3600)

    def page_title(self) -> str:
        return 'People'
