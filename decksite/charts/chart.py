import os.path
import pathlib
from typing import Dict

import matplotlib as mpl
# This has to happen before pyplot is imported to avoid needing an X server to draw the graphs.
# pylint: disable=wrong-import-position
mpl.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from decksite.data import deck
from shared import configuration, logger
from shared.pd_exception import DoesNotExistException, OperationalException

def cmc(deck_id: int, attempts: int = 0) -> str:
    if attempts > 3:
        msg = 'Unable to generate cmc chart for {id} in 3 attempts.'.format(id=deck_id)
        logger.error(msg)
        raise OperationalException(msg)
    path = determine_path(str(deck_id) + '-cmc.png')
    if acceptable_file(path):
        return path
    d = deck.load_deck(deck_id)
    costs: Dict[str, int] = {}
    for ci in d.maindeck:
        c = ci.card
        if c.is_land():
            continue
        if c.mana_cost is None:
            cost = '0'
        elif next((s for s in c.mana_cost if '{X}' in s), None) is not None:
            cost = 'X'
        else:
            converted = int(float(c.cmc))
            cost = '7+' if converted >= 7 else str(converted)
        costs[cost] = ci.get('n') + costs.get(cost, 0)
    path = image(path, costs)
    if acceptable_file(path):
        return path
    return cmc(deck_id, attempts + 1)

def image(path: str, costs: Dict[str, int]) -> str:
    ys = ['0', '1', '2', '3', '4', '5', '6', '7+', 'X']
    xs = [costs.get(k, 0) for k in ys]
    sns.set_style('white')
    sns.set(font='Concourse C3', font_scale=3)
    g = sns.barplot(x=ys, y=xs, palette=['#cccccc'] * len(ys)) # pylint: disable=no-member
    g.axes.yaxis.set_ticklabels([])
    rects = g.patches
    sns.set(font='Concourse C3', font_scale=2)
    for rect, label in zip(rects, xs):
        if label == 0:
            continue
        height = rect.get_height()
        g.text(rect.get_x() + rect.get_width()/2, height + 0.5, label, ha='center', va='bottom')
    g.margins(y=0, x=0)
    sns.despine(left=True, bottom=True)
    g.get_figure().savefig(path, transparent=True, pad_inches=0, bbox_inches='tight')
    plt.clf() # Clear all data from matplotlib so it does not persist across requests.
    return path

def determine_path(name: str) -> str:
    charts_dir = configuration.get_str('charts_dir')
    pathlib.Path(charts_dir).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(charts_dir):
        raise DoesNotExistException('Cannot store graph images because {charts_dir} does not exist.'.format(charts_dir=charts_dir))
    return os.path.join(charts_dir, name)

def acceptable_file(path: str) -> bool:
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) >= 6860: # This is a few bytes smaller than a completely empty graph on prod.
        return True
    logger.warning('Chart at {path} is suspiciously small.'.format(path=path))
    return False
