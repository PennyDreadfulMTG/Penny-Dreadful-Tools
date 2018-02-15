from flask import request, url_for
from flask_babel import gettext

from magic import tournaments
from shared.container import Container
from shared.database import sqlescape

from decksite.data import person
from decksite.database import db
from decksite.maintenance import squash_people
from decksite.view import View
from decksite import auth

# pylint: disable=no-self-use,too-many-instance-attributes
class LinkAccounts(View):
    def __init__(self):
        self.mtgo_name = auth.logged_person_mtgo_username()
        self.person = person.load_person_by_discord_id(auth.discord_id())
        self.form = request.form or Container()
        self.form.errors = Container()
        if self.person:
            if self.form.get('to_username', None) is None and self.person.tappedout_username is not None:
                self.form.to_username = self.person.tappedout_username
                self.disable_to = True
            if self.form.get('gf_username', None) is None and self.person.mtggoldfish_username is not None:
                self.form.gf_username = self.person.mtggoldfish_username
                self.disable_gf = True

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def subtitle(self):
        return gettext("Link accounts")

    def validate(self):
        if self.person:
            tapped_name = self.form.get('to_username', None)
            if tapped_name is not None and self.person.tappedout_username != tapped_name:
                tapped_user = person.load_person_by_tappedout_name(tapped_name)
                if self.person.tappedout_username is None and tapped_user is None:
                    self.form.errors.to_username = 'Could not find a TappedOut user called "{tapped_name}" in our database'.format(tapped_name=tapped_name)
                elif tapped_user.id != self.person.id:
                    self.form.errors.to_username = '"{tapped_name}" is already associated to another user.  If you believe this is in error, contact us.'.format(tapped_name=tapped_name)
                else:
                    squash_people.squash(self.person.id, tapped_user.id, "mtgo_username", "tappedout_username")
            mtggoldfish_name = self.form.get('gf_username', None)
            if mtggoldfish_name is not None and self.person.mtggoldfish_username != mtggoldfish_name:
                mtggoldfish_user = person.load_person_by_mtggoldfish_name(mtggoldfish_name)
                if self.person.mtggoldfish_username is None and mtggoldfish_user is None:
                    self.form.errors.to_username = 'Could not find a MTGGoldfish user called "{mtggoldfish_name}" in our database'.format(mtggoldfish_name=mtggoldfish_name)
                elif mtggoldfish_user.id != self.person.id:
                    self.form.errors.to_username = '"{mtggoldfish_name}" is already associated to another user.  If you believe this is in error, contact us.'.format(mtggoldfish_name=mtggoldfish_name)
                else:
                    squash_people.squash(self.person.id, mtggoldfish_user.id, "mtgo_username", "mtggoldfish_username")



