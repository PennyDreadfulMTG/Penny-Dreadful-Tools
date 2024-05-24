from decksite.view import View
from shared_web.menu import Menu


class Admin(View):
    def __init__(self, admin_menu: Menu) -> None:
        super().__init__()
        self.admin_menu = admin_menu

    def page_title(self) -> str:
        return 'Admin Menu'
