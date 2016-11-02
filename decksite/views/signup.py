from decksite.view import View

# pylint: disable=no-self-use
class SignUp(View):
    def __init__(self, form):
        self.form = form

    def subtitle(self):
        return 'League Sign Up'
