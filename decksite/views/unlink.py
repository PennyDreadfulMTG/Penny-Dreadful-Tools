from decksite.view import View


class Unlink(View):
    def __init__(self, num_affected_people: int | None = None, errors: list[str] | None = None) -> None:
        super().__init__()
        self.person_filter = 'discord'
        if num_affected_people is not None:
            self.message = f'{num_affected_people} were affected'
        self.errors = errors or []

    def page_title(self) -> str:
        return 'Unlink'
