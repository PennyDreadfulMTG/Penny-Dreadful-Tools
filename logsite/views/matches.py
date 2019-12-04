from flask import request, url_for

from shared_web.decorators import fill_args

from .. import APP, db
from ..data import match
from ..view import View


@APP.route('/formats/<format_name>/')
def show_format(format_name: str = None) -> str:
    view = Matches(format_name=format_name)
    return view.page()

@APP.route('/people/<person>/')
def show_person(person: str = None) -> str:
    view = Matches(person=person)
    return view.page()

@APP.route('/matches/')
def matches() -> str:
    view = Matches()
    return view.page()

# pylint: disable=no-self-use
class Matches(View):
    @fill_args('person', 'format_name', 'page')
    def __init__(self, person: str = None, format_name: str = None, page: str = '1') -> None:
        pagenum = int(page)
        query = match.Match.select()
        if person is not None:
            query = query.join(db.MatchPlayers).join(db.User).where(db.User.name == person)
        if format_name is not None:
            fmt = db.get_format(format_name)
            if fmt is not None:
                query = query.where(match.Match.format_id == fmt.id)
        recent = query.order_by(match.Match.id.desc()).paginate(pagenum, 20)

        self.matches = recent
        self.has_next = bool(recent)
        self.has_prev = pagenum > 1
        self.has_pagination = self.has_next or self.has_prev
        if self.has_next:
            self.next_url = url_for(request.endpoint, person=person, format_name=format_name, page=pagenum + 1)
        if self.has_prev:
            self.prev_url = url_for(request.endpoint, person=person, format_name=format_name, page=pagenum - 1)
