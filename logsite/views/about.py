from flask_babel import gettext

from logsite.view import View

from .. import APP


@APP.route('/about/')
def about() -> str:
    view = About()
    return view.page()

# pylint: disable=no-self-use
class About(View):
    def subtitle(self) -> str:
        return gettext('About')

    def languages(self) -> str:
        return ', '.join([locale.display_name for locale in APP.babel.list_translations()])
