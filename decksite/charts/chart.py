import os.path

import matplotlib as mpl
# This has to happen before pyplot is imported to avoid needing an X server to draw the graphs.
# pylint: disable=wrong-import-position
mpl.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from decksite.data import deck
from shared import configuration
from shared.pd_exception import DoesNotExistException

def cmc(deck_id):
    name = str(deck_id) + '-cmc.png'
    if not os.path.exists(configuration.get('charts_dir')):
        raise DoesNotExistException('Cannot store graph images because {dir} does not exist.'.format(dir=configuration.get('charts_dir')))
    path = os.path.join(configuration.get('charts_dir'), name)
    if os.path.exists(path):
        return path
    d = deck.load_deck(deck_id)
    costs = {}
    for ci in d.maindeck:
        c = ci.get('card')
        if c.is_land():
            continue
        if c.mana_cost is None:
            cost = '0'
        elif next((s for s in c.mana_cost if '{X}' in s), None) is not None:
            cost = 'X'
        else:
            cost = int(float(c.cmc))
            if cost >= 7:
                cost = '7+'
            cost = str(cost)
        costs[cost] = ci.get('n') + costs.get(cost, 0)
    return image(path, costs)

def image(path, costs):
    ys = ['0', '1', '2', '3', '4', '5', '6', '7+', 'X']
    xs = [costs.get(k, 0) for k in ys]
    sns.set(font_scale=3)
    sns.set_style('white')
    g = sns.barplot(ys, xs, palette=['grey'] * len(ys))
    g.axes.yaxis.set_ticklabels([])
    rects = g.patches
    sns.set(font_scale=2)
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
