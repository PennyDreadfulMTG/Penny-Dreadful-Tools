from logsite.view import View


# pylint: disable=no-self-use
class NotFound(View):
    def __init__(self, exception):
        self.exception = str(exception)
        self.card = None
        self.cards = [self.card]

    def message(self):
        return "We couldn't find that."

    def template(self):
        return 'error'

    def subtitle(self):
        return 'Not Found'
