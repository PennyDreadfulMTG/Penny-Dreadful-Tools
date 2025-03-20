from collections.abc import Iterable, Iterator, Sized
from dataclasses import dataclass, field

from flask import url_for

from shared.pd_exception import InvalidArgumentException


@dataclass
class Menu(Iterable['MenuItem'], Sized):
    menu: list['MenuItem'] = field(default_factory=list)
    current_endpoint: str | None = None

    def __post_init__(self) -> None:
        self.set_current(self)

    def set_current(self, menu: 'Menu') -> None:
        for item in menu:
            item.current = self.is_current(item)
            if item.has_submenu:
                self.set_current(item.submenu)

    def is_current(self, item: 'MenuItem') -> bool:
        return normalize_endpoint(item) == self.current_endpoint or self.current_endpoint in [normalize_endpoint(entry) for entry in item.submenu]

    def __iter__(self) -> Iterator['MenuItem']:
        return iter(self.menu)

    def __len__(self) -> int:
        return len(self.menu)

@dataclass
class Badge:
    url: str
    text: str
    class_name: str

@dataclass
class MenuItem:
    name: str
    endpoint: str = ''
    url: str = ''
    submenu: Menu = field(default_factory=Menu)
    badge: Badge | None = None
    permission_required: str | None = None
    current: bool = False

    def __post_init__(self) -> None:
        if (not self.endpoint and not self.url) or (self.endpoint and self.url):
            raise InvalidArgumentException("MenuItem must have either 'endpoint' or 'url', but not both.")

        if self.endpoint:
            self.url = url_for(self.endpoint)

    @property
    def has_submenu(self) -> bool:
        return len(self.submenu) > 0

    @property
    def is_external(self) -> bool:
        return self.url.startswith('http') and '://pennydreadfulmagic.com/' not in self.url

    @property
    def demimod_only(self) -> bool:
        return self.permission_required == 'demimod'

    @property
    def admin_only(self) -> bool:
        return self.permission_required == 'demimod' or self.permission_required == 'admin'

def normalize_endpoint(item: 'MenuItem') -> str:
    return item.endpoint.replace('seasons.', '').replace('.', '')
