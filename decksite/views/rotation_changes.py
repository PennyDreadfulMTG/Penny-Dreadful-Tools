from decksite.view import View

def first_time(c):
    return len({k:v for (k, v) in c['legalities'].items() if 'Penny Dreadful' in k}) == 1

# pylint: disable=no-self-use
class RotationChanges(View):
    def __init__(self, cards_in, cards_out, subtitle="Rotation Changes"):
        self.sections = []
        self.cards = cards_in + cards_out
        entries_in = [{'name': c.name, 'card': c, 'first_time': first_time(c)} for c in cards_in]
        entries_out = [{'name': c.name, 'card': c} for c in cards_out]
        self.sections.append({'name': 'New this season', 'entries': entries_in, 'num_entries': len(entries_in)})
        self.sections.append({'name': 'Rotated out', 'entries': entries_out, 'num_entries': len(entries_out)})
        self._subtitle = subtitle


    def subtitle(self):
        return self._subtitle
