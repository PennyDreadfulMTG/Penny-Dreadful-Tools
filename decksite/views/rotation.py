import datetime
import fileinput
import glob
import html
import os
from collections import Counter

from decksite.data import card
from decksite.view import View
from magic import multiverse, oracle, rotation
from shared import configuration, dtutil
from shared.pd_exception import DoesNotExistException


# pylint: disable=no-self-use
class Rotation(View):
    def __init__(self):
        until_full_rotation = rotation.next_rotation() - dtutil.now()
        until_supplemental_rotation = rotation.next_supplemental() - dtutil.now()
        in_rotation = False
        if until_full_rotation < datetime.timedelta(7):
            in_rotation = True
            self.rotation_msg = 'Full rotation is in progress, ends ' + dtutil.display_date(rotation.next_rotation(), 2)
        elif until_supplemental_rotation < datetime.timedelta(7):
            in_rotation = True
            self.rotation_msg = 'Supplemental rotation is in progress, ends ' + dtutil.display_date(rotation.next_supplemental(), 2)
        elif until_full_rotation < until_supplemental_rotation:
            self.rotation_msg = 'Full rotation is ' + dtutil.display_date(rotation.next_rotation(), 2)
        else:
            self.rotation_msg = 'Supplemental rotation is ' + dtutil.display_date(rotation.next_supplemental(), 2)
        if in_rotation:
            self.read_rotation_files()
        self.show_interesting = True

    def read_rotation_files(self):
        lines = []
        files = glob.glob(os.path.join(configuration.get('legality_dir'), "Run_*.txt"))
        self.cards = []
        if len(files) == 0:
            files = glob.glob(os.path.join(configuration.get('legality_dir'), "*.jar"))
            if len(files) == 0:
                raise DoesNotExistException('Invalid configuration.  Could not find Legality Checker')
            self.runs = 0
            self.runs_percent = 0
            return
        for line in fileinput.input(files):
            lines.append(line.strip())
        scores = Counter(lines).most_common()
        self.runs = scores[0][1]
        self.runs_percent = round(round(self.runs / 168, 2) * 100)
        self.cs = oracle.cards_by_name()
        for name, hits in scores:
            self.process_score(name, hits)

    def process_score(self, name, hits):
        playability = card.playability()
        remaining_runs = (168 - self.runs)
        name = html.unescape(name.encode('latin-1').decode('utf-8'))
        hits_needed = max(84 - hits, 0)
        c = self.cs.get(name)
        if c.layout not in multiverse.playable_layouts():
            return
        percent = round(round(hits / self.runs, 2) * 100)
        if remaining_runs == 0:
            percent_needed = 0
        else:
            percent_needed = round(round(hits_needed / remaining_runs, 2) * 100)
        if c is None:
            raise DoesNotExistException("Legality list contains unknown card '{name}'".format(name=name))
        if remaining_runs + hits < 84:
            status = 'Not Legal'
        elif hits >= 84:
            status = 'Legal'
        else:
            status = 'Undecided'
            hits = redact(hits)
            hits_needed = redact(hits_needed)
            percent = redact(percent)
            percent_needed = redact(percent_needed)
        c.update({
            'hits': hits,
            'hits_needed': hits_needed,
            'percent': percent,
            'percent_hits_needed': percent_needed,
            'status': status,
            'interestingness': rotation.interesting(playability, c)
        })
        self.cards.append(c)

    def subtitle(self):
        return 'Rotation'

def redact(num):
    return ''.join(['█' for _ in str(num)])
