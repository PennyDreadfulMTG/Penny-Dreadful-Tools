from flask import url_for

from shared_web.base_view import BaseView

from . import APP


# pylint: disable=no-self-use, too-many-public-methods
class View(BaseView):
    def home_url(self):
        return url_for('home')

    def css_url(self):
        return 'https://pennydreadfulmagic.com/static/css/pd.css'

    def tooltips_url(self):
        return url_for('static', filename='js/tooltips.js', v=self.commit_id())

    def js_url(self):
        return 'https://pennydreadfulmagic.com/static/js/pd.js'

    def js_extra_url(self):
        return None

    def menu(self):
        menu = [
            {'name': 'Home', 'url': url_for('home')},
            {'name': 'Matches', 'url': url_for('matches')},
            {'name': 'People', 'url': url_for('people')},
            {'name': 'About', 'url': url_for('about')},
        ]
        return menu

    def prepare(self):
        pass

    def favicon_url(self):
        return url_for('favicon', rest='.ico')

    def favicon_152_url(self):
        return url_for('favicon', rest='-152.png')

    def title(self):
        if not self.subtitle():
            return 'PDBot Logs'
        return '{subtitle} – PDBot Logs'.format(subtitle=self.subtitle())

    def subtitle(self):
        return None

    def commit_id(self) -> str:
        return APP.config['commit-id']
