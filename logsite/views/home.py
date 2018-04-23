from flask import url_for
from flask_babel import gettext

from logsite.view import View

from .. import APP, db
from ..data import match


@APP.route('/')
def home():
    view = Home()
    return view.page()


# pylint: disable=no-self-use
class Home(View):
    def __init__(self):
        pd = db.get_or_insert_format('PennyDreadful')
        self.matches = match.get_recent_matches_by_format(pd.id).paginate(per_page=10).items
        self.matches_url = url_for('matches')

    def subtitle(self):
        return None
