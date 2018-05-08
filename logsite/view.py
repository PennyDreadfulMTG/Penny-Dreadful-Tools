from flask import url_for

from shared_web.base_view import BaseView

from . import APP


# pylint: disable=no-self-use, too-many-public-methods
class View(BaseView):
    def home_url(self):
        return url_for('home')

    def js_extra_url(self):
        return None

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
