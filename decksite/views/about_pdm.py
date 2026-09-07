from flask import url_for
from flask_babel import gettext

from decksite.view import View


class AboutPdm(View):
    def __init__(self) -> None:
        super().__init__()
        self.about_url = url_for('about')

    def page_title(self) -> str:
        return gettext('About')
