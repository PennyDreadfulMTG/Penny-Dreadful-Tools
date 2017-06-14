import fileinput
import glob
import os
from collections import Counter

from magic import oracle
from shared import configuration

from decksite.view import View

# pylint: disable=no-self-use
class Rotation(View):
    def __init__(self):
        lines = []
        for line in fileinput.input(glob.glob(os.path.join(configuration.get('legality_dir'), "Run_*.txt"))):
            lines.append(line.strip())
        scores = Counter(lines).most_common()
        self.runs = scores[0][1]
        self.runs_percent = round(round(self.runs / 168, 2) * 100)
        self.cards = []
        cs = {c.name: c for c in oracle.load_cards()}
        remaining_runs = (168 - self.runs)
        for name, hits in scores:
            hits_needed = max(84 - hits, 0)
            card = cs.get(name)
            if remaining_runs + hits < 84:
                status = 'Not Legal'
            elif hits >= 84:
                status = 'Legal'
            else:
                status = 'Undecided'
            if card is not None: # BAKERT
                card.update({
                    'hits': hits,
                    'hits_needed': hits_needed,
                    'percent': round(round(hits / self.runs, 2) * 100),
                    'percent_hits_needed': round(round(hits_needed / remaining_runs, 2) * 100),
                    'status': status
                })
                self.cards.append(card)

    def subtitle(self):
        return 'Rotation'
