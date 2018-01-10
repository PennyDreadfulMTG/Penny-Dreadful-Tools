from decksite.view import View

# pylint: disable=no-self-use
class RotationChanges(View):
    def __init__(self, cards_in, cards_out, playability, speculation=False):
        self.playability = playability
        print(playability.keys())
        self.sections = []
        self.cards = cards_in + cards_out
        self.speculation = speculation
        entries_in = [{'name': c.name, 'card': c, 'interestingness': self.interesting(c)} for c in cards_in]
        entries_out = [{'name': c.name, 'card': c, 'interestingness': self.interesting(c, new=False)} for c in cards_out]
        self.sections.append({'name': 'New this season', 'entries': entries_in, 'num_entries': len(entries_in)})
        self.sections.append({'name': 'Rotated out', 'entries': entries_out, 'num_entries': len(entries_out)})
        self.speculation = speculation

    def subtitle(self):
        if self.speculation:
            return "Rotation speculation: what rotation would look like if it happened today"
        return "Rotation Changes"

    def interesting(self, c, new=True):
        if new and len({k: v for (k, v) in c['legalities'].items() if 'Penny Dreadful' in k}) == (0 if self.speculation else 1):
            return 'new'
        p = self.playability.get(c.name, 0)
        if p > 0.1:
            return 'heavily-played'
        elif p > 0.01:
            return 'moderately-played'
        return None
