from flask import url_for

from decksite import template

# pylint: disable=no-self-use
class View:
    def template(self):
        return self.__class__.__name__.lower()

    def content(self):
        return template.render(self)

    def page(self):
        return template.render_name('page', self)

    def home_url(self):
        return url_for('home')

    def css_url(self):
        return url_for('static', filename='css/pd.css')

    def favicon_url(self):
        return url_for('favicon', rest='.ico')

    def favicon_152_url(self):
        return url_for('favicon', rest='-152.png')

    def title(self):
        if not self.subtitle():
            return 'Penny Dreadful Decks'
        else:
            return '{subtitle} – Penny Dreadful Decks'.format(subtitle=self.subtitle())

    def subtitle(self):
        return None
