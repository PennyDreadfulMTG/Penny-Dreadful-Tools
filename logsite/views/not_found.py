from logsite.views.error import Error


class NotFound(Error):
    def message(self) -> str:
        return "We couldn't find that."

    def page_title(self) -> str:
        return 'Not Found'
