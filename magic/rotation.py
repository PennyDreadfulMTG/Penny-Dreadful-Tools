import datetime
import glob
import logging
import os
from collections import Counter

from magic import fetcher, layout, oracle, seasons
from magic.models import Card
from shared import configuration, dtutil, text
from shared import redis_wrapper as redis
from shared.fetch_tools import FetchException

TOTAL_RUNS = 168

def interesting(playability: dict[str, float], c: Card, speculation: bool = True, new: bool = True) -> str | None:
    if new and len({k: v for (k, v) in c['legalities'].items() if 'Penny Dreadful' in k}) == (0 if speculation else 1):
        return 'new'
    p = playability.get(c.name, 0)
    if p > 0.1:
        return 'heavily-played'
    if p > 0.01:
        return 'moderately-played'
    return None

def in_rotation() -> bool:
    if configuration.always_show_rotation.value:
        return True
    until_rotation = seasons.next_rotation() - dtutil.now()
    until_supplemental_rotation = seasons.next_supplemental() - dtutil.now()
    return until_rotation < datetime.timedelta(7) or until_supplemental_rotation < datetime.timedelta(7)

def files() -> list[str]:
    return sorted(glob.glob(os.path.expanduser(os.path.join(configuration.get_str('legality_dir'), 'Run_*.txt'))))

# Will raise if what you pass is not a valid path to a Run_xxx.txt file.
def run_number_from_path(path: str) -> int:
    return int(os.path.basename(path).split('.')[0].split('_')[1])

def last_run_number() -> int | None:
    try:
        return int(files()[-1].split('/')[-1].split('.')[0].split('_')[1])
    except IndexError:
        return None

def last_run_time() -> datetime.datetime | None:
    try:
        return dtutil.ts2dt(int(os.path.getmtime(files()[-1])))
    except (IndexError, OSError):
        return None

def read_rotation_files() -> tuple[int, int, list[Card]]:
    runs_str = redis.get_str('decksite:rotation:summary:runs')
    runs_percent_str = redis.get_str('decksite:rotation:summary:runs_percent')
    cards = redis.get_list('decksite:rotation:summary:cards')
    if runs_str is not None and runs_percent_str is not None and cards is not None:
        return int(runs_str), int(runs_percent_str), [Card(c, predetermined_values=True) for c in cards]
    return rotation_redis_store()

def rotation_redis_store() -> tuple[int, int, list[Card]]:
    lines = []
    fs = files()
    if len(fs) == 0:
        if not os.path.isdir(os.path.expanduser(configuration.get_str('legality_dir'))):
            print('WARNING: Could not find legality_dir.')
        return (0, 0, [])
    with open(fs[-1]) as f:
        latest_list = f.read().splitlines()
    cs = oracle.cards_by_name()
    for filename in fs:
        for line in get_file_contents(filename):
            line = text.sanitize(line)
            line = line.strip()
            if c := cs.get(line):
                line = c.name
            lines.append(line)
    scores = Counter(lines).most_common()
    runs = scores[0][1]
    runs_percent = runs_percentage(runs)
    cards = []
    card_names_by_status: dict[str, list[str]] = {}
    for name, hits in scores:
        c = process_score(name, hits, cs, runs, latest_list)
        if c is not None:
            cards.append(c)
            classify_by_status(c, card_names_by_status)
    redis.store('decksite:rotation:summary:runs', runs, ex=604800)
    redis.store('decksite:rotation:summary:runs_percent', runs_percent, ex=604800)
    redis.store('decksite:rotation:summary:cards', cards, ex=604800)
    if 'Undecided' in card_names_by_status:
        redis.sadd('decksite:rotation:summary:undecided', *card_names_by_status['Undecided'], ex=604800)
    if 'Legal' in card_names_by_status:
        redis.sadd('decksite:rotation:summary:legal', *card_names_by_status['Legal'], ex=604800)
    if 'Not Legal' in card_names_by_status:
        redis.sadd('decksite:rotation:summary:notlegal', *card_names_by_status['Not Legal'], ex=604800)
    return (runs, runs_percent, cards)

def get_file_contents(file: str) -> list[str]:
    key = f'decksite:rotation:file:{file}'
    contents = redis.get_list(key)
    if contents is not None:
        return contents
    with open(file) as f:
        contents = f.readlines()
    redis.store(key, contents, ex=604800)
    return contents

def clear_redis(clear_files: bool = False) -> None:
    redis.clear(*redis.keys('decksite:rotation:summary:*'))
    if clear_files:
        redis.clear(*redis.keys('decksite:rotation:file:*'))

def process_score(name: str, hits: int, cs: dict[str, Card], runs: int, latest_list: list[str]) -> Card | None:
    remaining_runs = TOTAL_RUNS - runs
    hits_needed = max(round(TOTAL_RUNS / 2 - hits), 0)
    c = cs.get(name)
    if c is None:
        # raise DoesNotExistException("Legality list contains unknown card '{name}'".format(name=name))
        return None
    if not layout.is_playable_layout(c.layout):
        return None
    percent = to_percent(hits / runs)
    if remaining_runs == 0:
        percent_needed = '0'
    else:
        percent_needed = str(to_percent(hits_needed / remaining_runs))
    if remaining_runs + hits < TOTAL_RUNS / 2:
        status = 'Not Legal'
    elif hits >= TOTAL_RUNS / 2:
        status = 'Legal'
    else:
        status = 'Undecided'
    hit_in_last_run = name in latest_list
    c.update({
        'hits': hits,
        'hits_needed': hits_needed,
        'percent': percent,
        'percent_needed': percent_needed,
        'status': status,
        'hit_in_last_run': hit_in_last_run,
    })
    return c

def classify_by_status(c: Card, card_names_by_status: dict[str, list[str]]) -> None:
    if c.status not in card_names_by_status:
        card_names_by_status[c.status] = []
    card_names_by_status[c.status].append(c.name)

async def rotation_hype_message(hype_command: bool) -> str | None:
    if not hype_command:
        clear_redis()
    runs, runs_percent, cs = read_rotation_files()
    runs_remaining = TOTAL_RUNS - runs
    threshold = int(TOTAL_RUNS / 2)
    newly_legal = [c for c in cs if c.hit_in_last_run and c.hits == threshold]
    newly_eliminated = [c for c in cs if not c.hit_in_last_run and c.status == 'Not Legal' and c.hits_needed == runs_remaining + 1]
    newly_hit = [c for c in cs if c.hit_in_last_run and c.hits == 1]
    num_undecided = len([c for c in cs if c.status == 'Undecided'])
    num_legal_cards = len([c for c in cs if c.status == 'Legal'])
    max_hits_in_undecided = max([c.hits for c in cs if c.status == 'Undecided'], default=0)
    soonest_new_card = threshold - max_hits_in_undecided
    s = f'Rotation run number {runs} completed.'
    if hype_command:
        s = f'{runs} rotation checks have completed.'
    s += f' Rotation is {runs_percent}% complete. {num_legal_cards} cards confirmed.'
    if len(newly_hit) > 0 and runs_remaining > runs:
        newly_hit_s = list_of_most_interesting(newly_hit)
        s += f'\nFirst hit for: {newly_hit_s}.'
    if len(newly_legal) > 0:
        newly_legal_s = list_of_most_interesting(newly_legal)
        s += f'\nConfirmed legal: {newly_legal_s}.'
    if len(newly_eliminated) > 0:
        newly_eliminated_s = list_of_most_interesting(newly_eliminated)
        s += f'\nEliminated: {newly_eliminated_s}.'
    s += f'\nUndecided: {num_undecided}.'
    s += f'\nNext new cards confirmed in {soonest_new_card} runs time.\n'
    if runs_percent >= 50:
        s += f"<{fetcher.decksite_url('/rotation/')}>"
    return s

def list_of_most_interesting(cs: list[Card]) -> str:
    max_shown = 25
    redis_key = 'discordbot:rotation:cardranks'
    ranks = redis.get_dict(redis_key)
    if not ranks:
        try:
            ranks = {c.get('name'): c.get('rank') for c in fetcher.cardfeed()['cards']}
            # Get all never-before-legal cards, give them a rank of 1 so they sort first
            never_before_legal = {c.name: 1 for c in oracle.load_cards(where="c.id NOT IN (SELECT card_id FROM card_legality WHERE format_id IN (SELECT id FROM format WHERE name LIKE 'Penny Dreadful%%'))")}
            ranks.update(never_before_legal)
            redis.store(redis_key, ranks, ex=86400)
        except FetchException as e:
            logging.warning(f'Failed to fetch card ranks: {e}')
    if ranks:
        cs.sort(key=lambda c: (ranks.get(c.name) or 999999, c.name))
    if len(cs) > max_shown:
        return ' • '.join(c.name for c in cs[0:max_shown]) + f' and {len(cs) - max_shown} more'
    return ' • '.join(c.name for c in cs)

def runs_percentage(runs: int) -> int:
    return to_percent(runs / TOTAL_RUNS)

def to_percent(val: float) -> int:
    return round(val * 100)
