from collections.abc import Iterable

from decksite.data.person import Person
from decksite.view import View
from shared import dtutil


class Sorters(View):
    def __init__(self, sorters: Iterable[Person]) -> None:
        super().__init__()
        for sorter in sorters:
            sorter.display_last_sorted = dtutil.display_date(sorter.last_sorted)
            sorter.date_sort = dtutil.dt2ts(sorter.last_sorted)
        self.people = sorters

    def page_title(self) -> str:
        return 'Archetype Sorters'
