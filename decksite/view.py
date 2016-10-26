from flask import url_for

from decksite import template

class View:
    def template(self):
        return self.__class__.__name__.lower()

    def page(self):
        return template.render_name('page', self, { 'content': template.render(self) })

    def home_url(self):
        return url_for('home')

    def css_url(self):
        return url_for('static', filename='css/pd.css')
