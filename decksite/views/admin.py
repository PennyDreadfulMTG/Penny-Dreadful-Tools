from decksite.view import View


class Admin(View):
    def __init__(self, admin_menu: list[dict[str, str]]) -> None:
        super().__init__()
        self.admin_menu = admin_menu

    def page_title(self) -> str:
        return 'Admin Menu'
