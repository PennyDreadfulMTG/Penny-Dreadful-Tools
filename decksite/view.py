from flask import url_for

from decksite import template

class View:
    def template(self):
        return self.__class__.__name__.lower()

    def page(self):
        context = {
            'home_url': url_for('home'),
            'css_url': url_for('static', filename='css/pd.css'),
            'content': template.render(self)
        }
        return template.render_name('page', self, context)
