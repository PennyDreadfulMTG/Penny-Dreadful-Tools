from logsite.views.error import Error


# pylint: disable=no-self-use
class InternalServerError(Error):
    def message(self):
        return 'Something went wrong.'

    def subtitle(self):
        return 'Internal Server Error'
