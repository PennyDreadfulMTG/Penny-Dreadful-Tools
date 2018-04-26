from decksite.view import View


# pylint: disable=no-self-use
class Admin(View):
    def __init__(self, admin_menu) -> None:
        super().__init__()
        self.admin_menu = admin_menu

    def page_title(self):
        return 'Admin Menu'
