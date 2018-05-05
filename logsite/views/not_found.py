from logsite.views.error import Error


# pylint: disable=no-self-use
class NotFound(Error):
    def message(self):
        return "We couldn't find that."

    def subtitle(self):
        return 'Not Found'
