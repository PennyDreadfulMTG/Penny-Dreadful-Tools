from flask import request, url_for

from .. import APP
from ..data import match
from ..view import View


@APP.route('/people/<person>/')
def show_person(person=None):
    view = Matches(person=person)
    return view.page()

@APP.route('/matches/')
def matches():
    view = Matches()
    return view.page()

# pylint: disable=no-self-use
class Matches(View):
    def __init__(self, person=None) -> None:
        if person is None:
            recent = match.get_recent_matches().paginate()
        else:
            recent = match.get_recent_matches_by_player(person).paginate()

        self.matches = recent.items
        self.has_next = recent.has_next
        self.has_prev = recent.has_prev
        if recent.has_next:
            self.next_url = url_for(request.endpoint, person=person, page=recent.next_num)
        if recent.has_prev:
            self.prev_url = url_for(request.endpoint, person=person, page=recent.prev_num)

    def subtitle(self):
        return None
