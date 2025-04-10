from logsite.views.error import Error


class BadRequest(Error):
    def message(self) -> str:
        return f"That doesn't look right.  {self.exception}"

    def page_title(self) -> str:
        return 'Bad Request'
