from decksite.view import View
from magic import rotation


# pylint: disable=no-self-use
class RotationChanges(View):
    def __init__(self, cards_in, cards_out, playability, speculation=False):
        self.sections = []
        self.cards = cards_in + cards_out
        entries_in = [{'name': c.name, 'card': c, 'interestingness': rotation.interesting(playability, c, speculation)} for c in cards_in]
        entries_out = [{'name': c.name, 'card': c, 'interestingness': rotation.interesting(playability, c, speculation, new=False)} for c in cards_out]
        self.sections.append({'name': 'New this season', 'entries': entries_in, 'num_entries': len(entries_in)})
        self.sections.append({'name': 'Rotated out', 'entries': entries_out, 'num_entries': len(entries_out)})
        self.speculation = speculation
        self.show_interesting = True

    def subtitle(self):
        if self.speculation:
            return 'Rotation Speculation'
        return 'Rotation Changes'
