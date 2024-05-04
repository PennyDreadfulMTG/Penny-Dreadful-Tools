from werkzeug.datastructures import ImmutableMultiDict

from shared.container import Container


class Form(Container):
    def __init__(self, form: ImmutableMultiDict) -> None:
        super().__init__()
        self.update(form.to_dict())
        self.errors: dict[str, str] = {}
        self.warnings: dict[str, str] = {}

    def validate(self) -> bool:
        self.do_validation()
        return len(self.errors) == 0
