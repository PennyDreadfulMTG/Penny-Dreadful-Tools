from flask import Response, redirect, url_for
from flask_babel import gettext

from logsite.view import View
from shared import dtutil

from .. import APP, stats


@APP.route('/stats/')
def old_charts() -> Response:
    return redirect(url_for('charts'))

@APP.route('/charts/')
def charts() -> str:
    view = Charts()
    return view.page()

# pylint: disable=no-self-use
class Charts(View):
    def subtitle(self) -> str:
        return gettext('Stats')

    def js_extra_url(self) -> str:
        return url_for('static', filename='js/charts.js', v=self.commit_id())

    def last_switcheroo(self) -> str:
        last_switcheroo = stats.calc_last_switcheroo()
        if last_switcheroo:
            diff = dtutil.dt2ts(dtutil.now()) - dtutil.dt2ts(last_switcheroo.start_time_aware())
            return dtutil.display_time(diff)
        return 'unknown'
