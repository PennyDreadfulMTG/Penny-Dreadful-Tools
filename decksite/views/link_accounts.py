from typing import Any

from flask import request
from flask_babel import gettext

from decksite import auth
from decksite.data import person
from decksite.view import View
from shared.container import Container
from shared.pd_exception import AlreadyExistsException


class LinkAccounts(View):
    def __init__(self) -> None:
        super().__init__()
        self.mtgo_name = auth.mtgo_username()
        self.person = person.maybe_load_person_by_discord_id(auth.discord_id())
        self.form = Container()
        for k in request.form.keys():  # type: ignore
            self.form[k] = request.form[k].strip()
        self.form.errors = Container()
        self.process()

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.person, attr)

    def page_title(self) -> str:
        return gettext('Link Accounts')

    def process(self) -> None:
        if not (self.person and self.person.mtgo_username) and self.form.get('mtgo_username', None):  # Not linked
            self.link_discord()

    def link_discord(self) -> None:
        did = auth.discord_id()
        if did is None:
            self.form.errors.mtgo_username = 'You are not logged into discord'
            return
        try:
            self.person = person.link_discord(self.form['mtgo_username'], did)
        except AlreadyExistsException:
            self.form.errors.mtgo_username = '{mtgo_username} is already connected to another discord account.'.format(mtgo_username=self.form['mtgo_username'])
