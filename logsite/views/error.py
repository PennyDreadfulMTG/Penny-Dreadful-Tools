from logsite.view import View


class Error(View):
    def __init__(self, exception: Exception) -> None:
        self.exception = str(exception)
        self.card = None
        self.cards = [self.card]

    def template(self) -> str:
        return 'error'
