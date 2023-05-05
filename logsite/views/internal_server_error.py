from logsite.views.error import Error


class InternalServerError(Error):
    def message(self) -> str:
        return 'Something went wrong.'

    def page_title(self) -> str:
        return 'Internal Server Error'
