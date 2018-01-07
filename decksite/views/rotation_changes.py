from decksite.view import View

def first_time(c, speculation):
    if speculation:
        t = 0
    else:
        t = 1
    return len({k:v for (k, v) in c['legalities'].items() if 'Penny Dreadful' in k}) == t

# pylint: disable=no-self-use
class RotationChanges(View):
    def __init__(self, cards_in, cards_out, speculation=False):
        self.sections = []
        self.cards = cards_in + cards_out
        entries_in = [{'name': c.name, 'card': c, 'first_time': first_time(c, speculation)} for c in cards_in]
        entries_out = [{'name': c.name, 'card': c} for c in cards_out]
        self.sections.append({'name': 'New this season', 'entries': entries_in, 'num_entries': len(entries_in)})
        self.sections.append({'name': 'Rotated out', 'entries': entries_out, 'num_entries': len(entries_out)})
        self.speculation = speculation


    def subtitle(self):
        if self.speculation:
            return "Rotation speculation: what rotation would look like if it happened today"
        else:
            return "Rotation Changes"
