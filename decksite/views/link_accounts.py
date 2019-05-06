from typing import Any, cast

from flask import request
from flask_babel import gettext

from decksite import auth
from decksite.data import person
from decksite.view import View
from shared.container import Container
from shared.pd_exception import AlreadyExistsException


# pylint: disable=no-self-use,too-many-instance-attributes
class LinkAccounts(View):
    def __init__(self) -> None:
        super().__init__()
        self.mtgo_name = auth.mtgo_username()
        self.person = person.maybe_load_person_by_discord_id(auth.discord_id())
        self.form = Container()
        for k in request.form.keys(): # type: List[str]
            self.form[k] = request.form[k].strip()
        self.form.errors = Container()
        if self.person and self.person.mtgo_username:
            if self.form.get('to_username', None) is None and self.person.tappedout_username is not None:
                self.form['to_username'] = self.person.tappedout_username
                self.disable_to = True
            if self.form.get('gf_username', None) is None and self.person.mtggoldfish_username is not None:
                self.form['gf_username'] = self.person.mtggoldfish_username
                self.disable_gf = True
        self.process()

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.person, attr)

    def page_title(self) -> str:
        return gettext('Link Accounts')

    def process(self) -> None:
        if self.person and self.person.mtgo_username:
            self.link_tappedout()
            self.link_mtggoldfish()
        elif self.form.get('mtgo_username', None): # Not linked
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

    def link_mtggoldfish(self) -> None:
        if self.person is None:
            return
        mtggoldfish_name = self.form.get('gf_username', None)
        if mtggoldfish_name and self.person.mtggoldfish_username != mtggoldfish_name:
            mtggoldfish_user = person.maybe_load_person_by_mtggoldfish_name(mtggoldfish_name)
            if mtggoldfish_user is None:
                self.form.errors.gf_username = 'Could not find an MTGGoldfish user called "{mtggoldfish_name}" in our database'.format(mtggoldfish_name=mtggoldfish_name)
            elif mtggoldfish_user.mtgo_username is not None:
                self.form.errors.gf_username = '"{mtggoldfish_name}" is already associated to another user.  If you believe this is in error, contact us.'.format(mtggoldfish_name=mtggoldfish_name)
            else:
                person.squash(self.person.id, mtggoldfish_user.id, 'mtgo_username', 'mtggoldfish_username')
                self.disable_gf = True

    def link_tappedout(self) -> None:
        if self.person is None:
            return
        tapped_name = self.form.get('to_username', None)
        if tapped_name and self.person.tappedout_username != tapped_name:
            tapped_user = person.maybe_load_person_by_tappedout_name(tapped_name)
            if tapped_user is None:
                self.form.errors.to_username = 'Could not find a TappedOut user called "{tapped_name}" in our database'.format(tapped_name=tapped_name)
            elif tapped_user.id is not None:
                self.form.errors.to_username = '"{tapped_name}" is already associated to another user.  If you believe this is in error, contact us.'.format(tapped_name=tapped_name)
            else:
                person.squash(self.person.id, cast(int, tapped_user.id), 'mtgo_username', 'tappedout_username')
                self.disable_to = True
