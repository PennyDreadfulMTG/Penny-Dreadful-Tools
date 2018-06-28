from decksite.view import View
from typing import List, Dict


# pylint: disable=no-self-use
class Admin(View):
    def __init__(self, admin_menu: List[Dict[str, str]]) -> None:
        super().__init__()
        self.admin_menu = admin_menu

    def page_title(self):
        return 'Admin Menu'
