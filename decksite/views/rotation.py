import fileinput
import glob
import html
import os
from collections import Counter

from magic import oracle
from shared import configuration
from shared.pd_exception import DoesNotExistException

from decksite.view import View

# pylint: disable=no-self-use
class Rotation(View):
    def __init__(self):
        lines = []
        files = glob.glob(os.path.join(configuration.get('legality_dir'), "Run_*.txt"))
        if len(files) == 0:
            files = glob.glob(os.path.join(configuration.get('legality_dir'), "*.jar"))
            if len(files) == 0:
                raise DoesNotExistException('Invalid configuration.  Could not find Legality Checker')
            self.runs = 0
            self.runs_percent = 0
            self.cards = []
            return
        for line in fileinput.input(files):
            lines.append(line.strip())
        scores = Counter(lines).most_common()
        self.runs = scores[0][1]
        self.runs_percent = round(round(self.runs / 168, 2) * 100)
        self.cards = []
        cs = oracle.cards_by_name()
        remaining_runs = (168 - self.runs)
        for name, hits in scores:
            name = html.unescape(name.encode('latin-1').decode('utf-8'))
            hits_needed = max(84 - hits, 0)
            card = cs.get(name)
            if card is None:
                raise DoesNotExistException("Legality list contains unknown card '{card}'".format(card=name))
            if remaining_runs + hits < 84:
                status = 'Not Legal'
            elif hits >= 84:
                status = 'Legal'
            else:
                status = 'Undecided'
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
