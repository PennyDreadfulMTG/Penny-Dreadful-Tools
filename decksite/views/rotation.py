import datetime
import os
from collections import Counter
from typing import List, Optional, Union

from decksite.data import card
from decksite.view import View
from magic import multiverse, oracle, rotation
from magic.models import Card
from shared import configuration, dtutil, redis, text
from shared.pd_exception import DoesNotExistException


# pylint: disable=no-self-use,too-many-instance-attributes
class Rotation(View):
    def __init__(self, interestingness: Optional[str] = None, rotation_query: Optional[str] = None, only_these: Optional[List[str]] = None) -> None:
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
        if interestingness:
            self.cards = [c for c in self.cards if c.get('interestingness') == interestingness]
        if only_these:
            self.cards = [c for c in self.cards if c.name in only_these]
        self.num_cards = len(self.cards)
        self.rotation_query = rotation_query or ''

    def read_rotation_files(self) -> None:
        lines = []
        files = rotation.files()
        if len(files) == 0:
            if not os.path.isdir(configuration.get_str('legality_dir')):
                raise DoesNotExistException('Invalid configuration.  Could not find legality_dir.')
            self.runs = 0
            self.runs_percent = 0
            return
        key = f'decksite:rotation:aggregate:{len(files)}'
        cached = redis.get_container_list(key)
        if cached is not None:
            self.cards = [card.Card(c) for c in cached]
            return
        self.latest_list = open(files[-1], 'r').read().splitlines()
        for filename in files:
            for line in self.get_file_contents(filename):
                line = text.sanitize(line)
                lines.append(line.strip())
        scores = Counter(lines).most_common()
        self.runs = scores[0][1]
        self.runs_percent = round(round(self.runs / 168, 2) * 100)
        self.cs = oracle.cards_by_name()
        for name, hits in scores:
            self.process_score(name, hits)
        redis.store(key, self.cards, ex=3600)

    def get_file_contents(self, file: str) -> List[str]:
        key = f'decksite:rotation:{file}'
        contents = redis.get_list(key)
        if contents is not None:
            return contents
        with open(file) as f:
            contents = f.readlines()
        redis.store(key, contents, ex=3600)
        return contents

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

    def page_title(self) -> str:
        return 'Rotation'

def redact(num: Union[str, int]) -> str:
    return ''.join(['█' for _ in str(num)])
