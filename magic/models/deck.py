from typing import Any, Dict, List

from magic import oracle
from magic.models import Card
from shared import dtutil
from shared.container import Container


# pylint: disable=too-many-instance-attributes
class Deck(Container):
    def __init__(self, params: Dict[str, Any]) -> None:
        super().__init__()
        for k in params.keys():
            self[k] = params[k]
        self.sorted = False

    def all_cards(self) -> List[Card]:
        cards: List[Card] = []
        for entry in self.maindeck + self.sideboard:
            cards += [entry.card] * entry['n']
        return cards

    def sort(self):
        if not self.sorted and (len(self.maindeck) > 0 or len(self.sideboard) > 0):
            self.maindeck.sort(key=lambda x: oracle.deck_sort(x.card))
            self.sideboard.sort(key=lambda x: oracle.deck_sort(x.card))
            self.sorted = True

    def is_in_current_run(self) -> bool:
        if ((self.wins or 0) + (self.draws or 0) + (self.losses or 0) >= 5) or self.retired:
            return False
        if self.competition_type_name != 'League':
            return False
        if self.competition_end_date < dtutil.now():
            return False
        return True

    def __str__(self):
        self.sort()
        s = ''
        for entry in self.maindeck:
            s += '{n} {name}\n'.format(n=entry['n'], name=entry['name'])
        s += '\n'
        for entry in self.sideboard:
            s += '{n} {name}\n'.format(n=entry['n'], name=entry['name'])
        return s.strip()

    def is_person_associated(self):
        return self.discord_id is not None
