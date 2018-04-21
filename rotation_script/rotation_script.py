import datetime
import glob
import os
from typing import Dict, Set

import ftfy

from magic import fetcher_internal, rotation
from price_grabber.parser import (PriceList, parse_cardhoarder_prices,
                                  parse_mtgotraders_prices)
from shared import configuration, dtutil

BLACKLIST: Set[str] = set()
WHITELIST: Set[str] = set()

def run() -> None:
    all_prices = {}
    for url in configuration.get_list('cardhoarder_urls'):
        s = fetcher_internal.fetch(url)
        s = ftfy.fix_encoding(s)
        all_prices[url] = parse_cardhoarder_prices(s)
    url = configuration.get_str('mtgotraders_url')
    if url:
        s = fetcher_internal.fetch(url)
        all_prices['mtgotraders'] = parse_mtgotraders_prices(s)

    process(all_prices)

def process(all_prices: Dict[str, PriceList]) -> None:
    seen_sets: Set[str] = set()
    used_sets: Set[str] = set()

    hits: Set[str] = set()
    for code in all_prices:
        prices = all_prices[code]
        for name, p, mtgo_set in prices:
            cents = int(float(p) * 100)
            seen_sets.add(mtgo_set)
            if cents <= 1 and is_good_set(mtgo_set):
                hits.add(name)
                used_sets.add(mtgo_set)
    ignored = seen_sets - used_sets
    process_sets(seen_sets, used_sets, hits, ignored)

def process_sets(seen_sets: Set[str], used_sets: Set[str], hits: Set[str], ignored: Set[str]) -> None:
    files = glob.glob(os.path.join(configuration.get_str('legality_dir'), 'Run_*.txt'))
    n = len(files) + 1
    path = os.path.join(configuration.get_str('legality_dir'), 'Run_{n}.txt').format(n=n)
    h = open(path, mode='w', encoding='utf-8')
    for card in hits:
        line = card + '\n'
        h.write(line)
    h.close()
    print('Run {n} completed, with {ccards} cards from {csets}/{tsets} sets'.format(n=n, ccards=len(hits), csets=len(used_sets), tsets=len(seen_sets)))
    print('Used:    {sets}'.format(sets=repr(used_sets)))
    print('Missed:  {sets}'.format(sets=repr(ignored)))

def is_good_set(setname: str) -> bool:
    if not BLACKLIST and not WHITELIST:
        supplimental = (rotation.next_supplemental() - dtutil.now()) < datetime.timedelta(7)
        if supplimental:
            WHITELIST.add(rotation.last_rotation_ex()['mtgo_code'])
        else:
            BLACKLIST.add(rotation.next_rotation_ex()['mtgo_code'])
    if setname in BLACKLIST:
        return False
    elif setname in WHITELIST:
        return True
    return not WHITELIST
