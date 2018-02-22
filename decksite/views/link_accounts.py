from flask import request
from flask_babel import gettext

from decksite import auth
from decksite.data import deck, person
from decksite.database import db
from decksite.maintenance import squash_people
from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use,too-many-instance-attributes
class LinkAccounts(View):
    def __init__(self):
        self.mtgo_name = auth.logged_person_mtgo_username()
        self.person = person.load_person_by_discord_id(auth.discord_id())
        self.form = Container()
        for k in request.form.keys():
            self.form[k] = request.form[k]
        self.form.errors = Container()
        if self.person:
            if self.form.get('to_username', None) is None and self.person.tappedout_username is not None:
                self.form['to_username'] = self.person.tappedout_username
                self.disable_to = True
            if self.form.get('gf_username', None) is None and self.person.mtggoldfish_username is not None:
                self.form['gf_username'] = self.person.mtggoldfish_username
                self.disable_gf = True
        self.validate()

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def subtitle(self):
        return gettext("Link accounts")

    def validate(self):
        if self.person:
            self.link_tappedout()
            self.link_mtggoldfish()
        else: # Not linked
            self.link_discord()

    def link_discord(self):
        p = deck.get_or_insert_person_id(self.form['mtgo_username'], None, None)
        p = person.load_person(p)
        if p.discord_id is None:
            sql = 'UPDATE person SET discord_id = ? WHERE id = ?'
            db().execute(sql, [auth.discord_id(), p.id])
            self.person = p
        else:
            self.form.errors.mtgo_username = '{mtgo_username} is already connected to another discord account.'.format(mtgo_username=self.form['mtgo_username'])

    def link_mtggoldfish(self):
        mtggoldfish_name = self.form.get('gf_username', None)
        if mtggoldfish_name is not None and self.person.mtggoldfish_username != mtggoldfish_name:
            mtggoldfish_user = person.load_person_by_mtggoldfish_name(mtggoldfish_name)
            if self.person.mtggoldfish_username is None and mtggoldfish_user is None:
                self.form.errors.gf_username = 'Could not find a MTGGoldfish user called "{mtggoldfish_name}" in our database'.format(mtggoldfish_name=mtggoldfish_name)
            elif mtggoldfish_user.mtgo_username is not None:
                self.form.errors.gf_username = '"{mtggoldfish_name}" is already associated to another user.  If you believe this is in error, contact us.'.format(mtggoldfish_name=mtggoldfish_name)
            else:
                squash_people.squash(self.person.id, mtggoldfish_user.id, "mtgo_username", "mtggoldfish_username")
                self.disable_gf = True

    def link_tappedout(self):
        tapped_name = self.form.get('to_username', None)
        if tapped_name is not None and self.person.tappedout_username != tapped_name:
            tapped_user = person.load_person_by_tappedout_name(tapped_name)
            if self.person.tappedout_username is None and tapped_user is None:
                self.form.errors.to_username = 'Could not find a TappedOut user called "{tapped_name}" in our database'.format(tapped_name=tapped_name)
            elif tapped_user.id is not None:
                self.form.errors.to_username = '"{tapped_name}" is already associated to another user.  If you believe this is in error, contact us.'.format(tapped_name=tapped_name)
            else:
                squash_people.squash(self.person.id, tapped_user.id, "mtgo_username", "tappedout_username")
                self.disable_to = True
