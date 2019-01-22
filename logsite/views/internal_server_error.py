from logsite.views.error import Error


# pylint: disable=no-self-use
class InternalServerError(Error):
    def message(self) -> str:
        return 'Something went wrong.'

    def subtitle(self) -> str:
        return 'Internal Server Error'
