from flask_babel import gettext

from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class SignUp(LeagueForm):
    def subtitle(self):
        return '{league} Sign Up'.format(league=self.league['name'])

    def TT_MTGOTRADERS_SIGNUP_TIK(self):
        return gettext('When you complete a five match league run for the first time ever you will get 1 tik credit with MTGO Traders.')

    def TT_MTGO_USERNAME(self):
        return gettext('Magic Online Username')

    def TT_DECK_NAME(self):
        return gettext('Deck Name')

    def TT_DECKLIST(self):
        return gettext('Decklist')

    def TT_ENTER_OR_UPLOAD(self):
        return gettext('Enter or upload your decklist')

    def TT_SIGNUP(self):
        return gettext('Sign Up')
