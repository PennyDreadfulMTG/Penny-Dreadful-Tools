from typing import List, Sequence

from flask import url_for
from werkzeug.datastructures import ImmutableMultiDict

from decksite.data.person import Person
from decksite.view import View
from decksite.views.league_form import LeagueForm
from shared.container import Container


# pylint: disable=no-self-use
class AdminRetire(LeagueForm):
    def __init__(self, form: ImmutableMultiDict) -> None:
        super().__init__(form)
        self.logout_url = url_for('logout', target='retire')

    def page_title(self) -> str:
        return 'Retire Deck'
