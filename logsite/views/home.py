# type: ignore

from flask import url_for

from logsite.view import View

from .. import APP, db
from ..data import match


@APP.route('/')
def home() -> str:
    view = Home()
    return view.page()


class Home(View):
    def __init__(self) -> None:
        super().__init__()
        pd = db.get_or_insert_format('PennyDreadful')
        self.matches = match.get_recent_matches_by_format(pd.id).paginate(per_page=10).items
        self.matches_url = url_for('matches')

    def page_title(self) -> str:
        return 'Latest Matches'
