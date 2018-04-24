from flask import url_for
from flask_babel import gettext

from logsite.view import View

from .. import APP


@APP.route('/stats/')
def charts():
    view = Charts()
    return view.page()

# pylint: disable=no-self-use
class Charts(View):
    def subtitle(self) -> str:
        return gettext('Stats')

    def js_extra_url(self):
        return url_for('static', filename='js/charts.js', v=self.commit_id())
