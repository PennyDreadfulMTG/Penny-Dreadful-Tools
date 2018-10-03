import datetime
import fileinput
import os
from collections import Counter
from typing import List, Union

from decksite.data import card
from decksite.view import View
from magic import multiverse, oracle, rotation
from magic.models.card import Card
from shared import configuration, dtutil, redis, text
from shared.pd_exception import DoesNotExistException


# pylint: disable=no-self-use,too-many-instance-attributes
class Rotation(View):
    def __init__(self) -> None:
        super().__init__()
        self.playability = card.playability()
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
        self.cards: List[Card] = []
        if in_rotation:
            self.read_rotation_files()
        self.show_interesting = True

    def read_rotation_files(self) -> None:
        lines = []
        files = rotation.files()
        if len(files) == 0:
            if not os.path.isdir(configuration.get_str('legality_dir')):
                raise DoesNotExistException('Invalid configuration.  Could not find legality_dir.')
            self.runs = 0
            self.runs_percent = 0
            return
        latest_file = files[-1]
        redis_key = f'decksite:scores:{latest_file}'
        scores = redis.get_list(redis_key)
        self.latest_list = open(latest_file, 'r').read().splitlines()
        if scores is None:
            for line in fileinput.FileInput(files):
                line = text.sanitize(line)
                lines.append(line.strip())
            scores = Counter(lines).most_common()
            redis.store(redis_key, scores)
        self.runs = scores[0][1]
        self.runs_percent = round(round(self.runs / 168, 2) * 100)
        self.cs = oracle.cards_by_name()
        for name, hits in scores:
            self.process_score(name, hits)

    def process_score(self, name: str, hits: int) -> None:
        remaining_runs = (168 - self.runs)
        hits_needed = max(84 - hits, 0)
        c = self.cs[name]
        if c.layout not in multiverse.playable_layouts():
            return
        percent = round(round(hits / self.runs, 2) * 100)
        if remaining_runs == 0:
            percent_needed = '0'
        else:
            percent_needed = str(round(round(hits_needed / remaining_runs, 2) * 100))
        if c is None:
            raise DoesNotExistException("Legality list contains unknown card '{name}'".format(name=name))
        if remaining_runs + hits < 84:
            status = 'Not Legal'
        elif hits >= 84:
            status = 'Legal'
        else:
            status = 'Undecided'
        hit_in_last_run = name in self.latest_list
        c.update({
            'hits': redact(hits) if status == 'Undecided' else hits,
            'hits_needed': redact(hits_needed) if status == 'Undecided' else hits_needed,
            'percent': redact(percent) if status == 'Undecided' else percent,
            'percent_hits_needed': redact(percent_needed) if status == 'Undecided' else percent_needed,
            'status': status,
            'interestingness': rotation.interesting(self.playability, c),
            'hit_in_last_run': hit_in_last_run
        })
        self.cards.append(c)

    def page_title(self):
        return 'Rotation'

def redact(num: Union[str, int]) -> str:
    return ''.join(['█' for _ in str(num)])
