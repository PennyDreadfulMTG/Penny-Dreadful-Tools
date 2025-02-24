import asyncio
import datetime
import fileinput
import functools
import glob
import os
import pathlib
import shutil
import subprocess
from collections import Counter

import ftfy
import sentry_sdk

from magic import card_price, fetcher, rotation, seasons
from price_grabber.parser import PriceListType, parse_cardhoarder_prices
from shared import configuration, decorators, dtutil, fetch_tools, repo, sentry, text
from shared import redis_wrapper as redis
from shared.pd_exception import NotConfiguredException

TIME_UNTIL_FULL_ROTATION = seasons.next_rotation() - dtutil.now()
TIME_SINCE_FULL_ROTATION = dtutil.now() - seasons.last_rotation()
TIME_UNTIL_SUPPLEMENTAL_ROTATION = seasons.next_supplemental() - dtutil.now()
TIME_SINCE_SUPPLEMENTAL_ROTATION = dtutil.now() - seasons.last_supplemental()
TIME_UNTIL_ROTATION = min(TIME_UNTIL_FULL_ROTATION, TIME_UNTIL_SUPPLEMENTAL_ROTATION)
TIME_SINCE_ROTATION = min(TIME_SINCE_FULL_ROTATION, TIME_SINCE_SUPPLEMENTAL_ROTATION)
BANNED_CARDS = ['Cleanse', 'Crusade']  # These cards are banned, even in Freeform

@decorators.interprocess_locked('.rotation.lock')
@sentry.monitor('rotation_script')
def run() -> None:
    files = rotation.files()
    n = len(files)
    time_until = TIME_UNTIL_ROTATION - datetime.timedelta(weeks=1)
    if n >= rotation.TOTAL_RUNS:
        print('It is the moment of discovery, the triumph of the mind, and the end of this rotation.')
        if TIME_SINCE_ROTATION > datetime.timedelta(7):
            dirname = os.path.join(configuration.get_str('legality_dir'), 'arc_' + seasons.last_rotation_ex().code.lower())
            if not os.path.exists(dirname):
                os.mkdir(dirname)
            all_files = glob.glob(os.path.expanduser(os.path.join(configuration.get_str('legality_dir'), '*.txt')))
            for f in all_files:
                os.rename(f, os.path.join(dirname, os.path.basename(f)))
        return

    if n == 0 and TIME_UNTIL_ROTATION > datetime.timedelta(7):
        print('The monks of the North Tree rarely saw their kodama until the rotation, when it woke like a slumbering, angry bear.')
        print(f'ETA: {dtutil.display_time(int(time_until.total_seconds()))}')
        return

    if n == 0:
        rotation.clear_redis(clear_files=True)
        try:
            url = f'{fetcher.decksite_url()}/api/rotation/clear_cache?hard=1'
            fetch_tools.fetch(url)
        except Exception as c:
            print(c, flush=True)

    all_prices = {}
    if not configuration.cardhoarder_urls.get():
        raise NotConfiguredException('Did not find any Cardhoarder URLs')
    for url in configuration.cardhoarder_urls.get():
        s = fetch_tools.fetch(url)
        s = ftfy.fix_encoding(s)
        all_prices[url] = parse_cardhoarder_prices(s)

    run_number = process(all_prices)

    try:
        url = f'{fetcher.decksite_url()}/api/rotation/clear_cache'
        fetch_tools.fetch(url)
    except Exception as c:
        print(c, flush=True)

    if run_number == rotation.TOTAL_RUNS:
        make_final_list()
        do_push()

def process(all_prices: dict[str, PriceListType]) -> int:
    seen_sets: set[str] = set()
    used_sets: set[str] = set()

    hits: set[str] = set()
    for code in all_prices:
        prices = all_prices[code]
        for name, p, mtgo_set in prices:
            if name in BANNED_CARDS:
                continue
            cents = int(float(p) * 100)
            seen_sets.add(mtgo_set)
            if cents <= card_price.MAX_PRICE_CENTS and is_good_set(mtgo_set):
                hits.add(name)
                used_sets.add(mtgo_set)
    ignored = seen_sets - used_sets
    return process_sets(seen_sets, used_sets, hits, ignored)


def process_sets(seen_sets: set[str], used_sets: set[str], hits: set[str], ignored: set[str]) -> int:
    files = rotation.files()
    n = len(files) + 1
    legality_dir = configuration.get_str('legality_dir')
    path = os.path.join(legality_dir, 'Run_{n}.txt').format(n=str(n).zfill(3))
    if not os.path.exists(legality_dir):
        os.makedirs(legality_dir)
    path = os.path.expanduser(path)
    h = open(path, mode='w', encoding='utf-8')
    for card in hits:
        line = card + '\n'
        h.write(line)
    h.close()
    print(f'Run {n} completed, with {len(hits)} cards from {len(used_sets)}/{len(seen_sets)} sets', flush=True)
    print(f'Used:    {repr(used_sets)}', flush=True)
    print(f'Missed:  {repr(ignored)}', flush=True)
    return n

@functools.cache
def is_supplemental() -> bool:
    return TIME_UNTIL_SUPPLEMENTAL_ROTATION < datetime.timedelta(7) or abs(TIME_SINCE_SUPPLEMENTAL_ROTATION) < datetime.timedelta(1)

def is_good_set(set_code: str) -> bool:
    if is_supplemental():
        upcoming_supp_set = seasons.next_supplemental_ex()
        assert upcoming_supp_set is not None
        return set_code == upcoming_supp_set.mtgo_code
    return True  # Supplemental sets are too far in the future to be priced, so we just accept everything

def make_final_list() -> None:
    _num, planes, _res = fetcher.search_scryfall('t:plane%20or%20t:phenomenon', True)
    bad_names = planes
    bad_names.extend(BANNED_CARDS)
    renames = prepare_flavornames()

    files = rotation.files()
    lines: list[str] = []
    for line in fileinput.input(files):
        line = text.sanitize(line)
        if line.strip() in bad_names:
            continue
        if line.strip() in renames:
            line = renames[line.strip()] + '\n'
        lines.append(line)
    scores = Counter(lines).most_common()

    passed: list[str] = []
    for name, count in scores:
        if count >= rotation.TOTAL_RUNS / 2:
            passed.append(name)
    final = list(passed)
    if is_supplemental():
        temp = set(passed)
        legal_cards = asyncio.get_event_loop().run_until_complete(fetcher.legal_cards_async())
        final = list(temp.union([c + '\n' for c in legal_cards]))

    final.sort()
    h = open(os.path.join(configuration.get_str('legality_dir'), 'legal_cards.txt'), mode='w', encoding='utf-8')
    h.write(''.join(final))
    h.close()
    print(f'Generated legal_cards.txt.  {len(passed)}/{len(scores)} cards.', flush=True)
    if is_supplemental():
        setcode = seasons.last_rotation_ex().mtgo_code
    else:
        setcode = seasons.next_rotation_ex().mtgo_code
    h = open(os.path.join(configuration.get_str('legality_dir'), f'{setcode}_legal_cards.txt'), mode='w', encoding='utf-8')
    h.write(''.join(final))
    h.close()

def prepare_flavornames() -> dict[str, str]:
    _num, _names, flavored = fetcher.search_scryfall('is:flavor_name', True)
    renames = {}
    for c in flavored:
        if c['layout'] == 'reversible_card':
            try:
                renames[c['card_faces'][0]['flavor_name']] = c['card_faces'][0]['name']
                renames[c['card_faces'][1]['flavor_name']] = c['card_faces'][1]['name']
            except KeyError:
                pass
        else:
            # So far, we don't need to worry about DFCs with flavor names, as none are available on MTGO.
            # In the future, we may need to adjust this code to match pricefiles
            renames[c.get('flavor_name') or c['card_faces'][0].get('flavor_name')] = c['name']
    return renames

def do_push() -> None:
    print('Pushing to Github...', flush=True)
    gh_repo = os.path.join(configuration.get_str('legality_dir'), 'gh_pages')
    if not os.path.exists(gh_repo):
        subprocess.run(['git', 'clone', 'https://github.com/PennyDreadfulMTG/pennydreadfulmtg.github.io.git', gh_repo], check=True)
    else:
        os.chdir(gh_repo)
        subprocess.run(['git', 'pull'], check=True)

    if is_supplemental():
        setcode = seasons.last_rotation_ex().mtgo_code
        rottype = 'supplemental'
    else:
        setcode = seasons.next_rotation_ex().mtgo_code
        rottype = 'rotation'

    files = ['legal_cards.txt', f'{setcode}_legal_cards.txt']
    for fn in files:
        source = os.path.join(configuration.get_str('legality_dir'), fn)
        dest = os.path.join(gh_repo, fn)
        shutil.copy(source, dest)

    os.chdir(gh_repo)
    subprocess.run(['git', 'add'] + files, check=True)
    subprocess.run(['git', 'commit', '-m', f'{setcode} {rottype}'], check=True)
    try:
        subprocess.run(['git', 'push'], check=True)
    except Exception as c:
        print(c, flush=True)
        sentry_sdk.capture_exception(c)
    print('done!\nGoing through checklist...', flush=True)
    checklist = f"""{setcode} {rottype} checklist

https://pennydreadfulmagic.com/admin/rotation/

- [ ] upload legal_cards.txt to S3 (set Content-Type to 'text/plain; charset=utf-8' in Metadata, System)
- [ ] upload {setcode}_legal_cards.txt to S3 (set Content-Type to 'text/plain; charset=utf-8' in Metadata, System)
- [ ] ping scryfall
- [ ] email mtggoldfish
"""
    print('Rebooting Discord bot...', flush=True)
    if redis.get_str('discordbot:commit_id'):
        redis.store('discordbot:do_reboot', True)
        print('Done!', flush=True)
        checklist += '- [x] restart discordbot\n'
    else:
        checklist += '- [ ] restart discordbot\n'
        print('Added to checklist!', flush=True)
    ds = os.path.expanduser('/home/pdadmin/decksite/')
    failed = False
    try:
        if os.path.exists(ds):
            print('Calling Post Rotation...', flush=True)
            os.chdir(ds)
            subprocess.run(['python3', 'run.py', 'maintenance', 'post_rotation'], check=True)
            checklist += '- [x] run post_rotation\n'
        else:
            failed = True
    except Exception:
        failed = True
    if failed:
        checklist += '- [ ] run post_rotation\n'

    checklist += '- [ ] Update Gatherling legal cards list\n'

    for path in ['/etc/uwsgi/vassals/decksite.ini', '/home/discord/vassals/decksite.ini']:
        srv = pathlib.Path(path)
        if srv.exists():
            print(f'touching {path}', flush=True)
            srv.touch()
            break
    else:
        checklist += '- [ ] touch /etc/uwsgi/vassals/decksite.ini\n'
    print('Sending checklist to Github...', flush=True)
    repo.create_issue(checklist, 'rotation script', 'rotation')
    print('Done!', flush=True)
