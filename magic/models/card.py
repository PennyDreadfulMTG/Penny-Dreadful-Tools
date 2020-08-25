from typing import Any, Dict, List, Optional, cast

from shared import dtutil
from shared.container import Container


class Card(Container):
    def __init__(self, params: Dict[str, Any], predetermined_values: bool = False) -> None:
        super().__init__()
        for k in params.keys():
            if predetermined_values:
                setattr(self, k, params[k])
            else:
                setattr(self, k, determine_value(k, params))
        if not hasattr(self, 'names'):
            setattr(self, 'names', [self.name])

    def is_double_sided(self) -> bool:
        return self.layout in ['transform', 'meld']

    def is_creature(self) -> bool:
        return 'Creature' in self.type_line

    def is_land(self) -> bool:
        return 'Land' in self.type_line

    def is_spell(self) -> bool:
        return not self.is_creature() and not self.is_land()

    def is_split(self) -> bool:
        return self.name.find('//') >= 0

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: Any) -> bool:
        if isinstance(self, other.__class__):
            return self.name == other.name
        return False

class Printing(Container):
    pass

def determine_value(k: str, params: Dict[str, Any]) -> Any:
    v = params[k]
    if k in ('names', 'mana_cost'):
        return cast(str, v).split('|') if v is not None else None
    if k == 'legalities':
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
        description, classification, last_confirmed, url, from_bug_blog, bannable_str = b.split('|')
        bb = from_bug_blog == '1'
        bannable = bannable_str == '1'
        bug = {'description': description, 'classification': classification, 'last_confirmed': dtutil.ts2dt(int(last_confirmed)), 'url': url, 'from_bug_blog': bb, 'bannable': bannable}
        v.append(bug)
    if v:
        return v
    return None
