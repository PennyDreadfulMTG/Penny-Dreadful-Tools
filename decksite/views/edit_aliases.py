from decksite.view import View
from shared.container import Container


class EditAliases(View):
    def __init__(self, aliases: list[Container]) -> None:
        super().__init__()
        for entry in aliases:
            if entry.mtgo_username:
                entry.person_url = f'/people/{entry.mtgo_username.lower()}/'
            else:
                entry.person_url = f'/people/id/{entry.person_id}/'
        self.person_filter = 'all'
        self.aliases = aliases

    def page_title(self) -> str:
        return 'Edit Aliases'
