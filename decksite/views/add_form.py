from decksite.view import View


class AddForm(View):
    def __init__(self):
        super().__init__()
        self.error = ''
