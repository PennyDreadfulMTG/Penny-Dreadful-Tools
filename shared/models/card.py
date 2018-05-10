from typing import Any, cast, Dict, List, Optional

from shared import dtutil
from shared.container import Container

class Card(Container):
    def __init__(self, params: Dict[str, Any]) -> None:
        super().__init__()
        for k in params.keys():
            setattr(self, k, determine_value(k, params))
        if not self.names:
            setattr(self, 'names', [self.name])

    def is_creature(self) -> bool:
        return 'Creature' in self.type

    def is_land(self) -> bool:
        return 'Land' in self.type

    def is_spell(self) -> bool:
        return not self.is_creature() and not self.is_land()

    def is_split(self) -> bool:
        return self.name.find('//') >= 0

def determine_value(k: str, params: Dict[str, Any]) -> Any:
    v = params[k]
    if k == 'names' or k == 'mana_cost':
        return cast(str, v).split('|') if v is not None else None
    elif k == 'legalities':
        v = determine_legalities(cast(str, v))
    elif k == 'bugs':
        v = determine_bugs(cast(str, v))
    return v

def determine_legalities(s: Optional[str]) -> Dict[str, str]:
    if s is None:
        return {}
    formats = s.split(',')
    v = {}
    for f in formats:
        name, status = f.split(':')
        v[name] = status
    return v

def determine_bugs(s: str) -> Optional[List[Dict[str, object]]]:
    if s is None:
        return None
    bugs = s.split('_SEPARATOR_')
    v = []
    for b in bugs:
        description, classification, last_confirmed, url, from_bug_blog = b.split('|')
        bb = from_bug_blog == '1'
        bug = {'description': description, 'classification': classification, 'last_confirmed': dtutil.ts2dt(int(last_confirmed)), 'url': url, 'from_bug_blog': bb}
        v.append(bug)
    if v:
        return v
    return None
