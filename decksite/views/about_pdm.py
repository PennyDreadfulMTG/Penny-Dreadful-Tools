from flask import url_for

from decksite.view import View

# pylint: disable=no-self-use
class AboutPdm(View):
    def __init__(self):
        self.about_url = url_for('about')

    def subtitle(self):
        return 'About'
