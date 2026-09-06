from flask_babel import gettext

from logsite.view import View

from .. import APP


@APP.route('/about/')
def about() -> str:
    view = About()
    return view.page()


class About(View):
    def page_title(self) -> str:
        return gettext('About')
