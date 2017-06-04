import os.path

import matplotlib as mpl
# This has to happen before pyplot is imported to avoid needing an X server to draw the graphs.
# pylint: disable=wrong-import-position
mpl.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from decksite.data import deck
from shared import configuration

IMG_DIR = os.path.join('decksite', configuration.get('image_dir'))
if not os.path.exists(IMG_DIR):
    os.mkdir(IMG_DIR)

def cmc(deck_id):
    name = str(deck_id) + '-cmc.png'
    path = os.path.join(IMG_DIR, name)
    flask_path = os.path.join(configuration.get('image_dir'), name)
    if os.path.exists(path):
        return flask_path
    d = deck.load_deck(deck_id)
    costs = {}
    for ci in d.maindeck:
        if not ci.get('card').is_land():
            cost = int(float(ci.get('card').cmc)) # Invalid for Unglued half costs.
            costs[cost] = ci.get('n') + costs.get(cost, 0)
    image(path, costs)
    return flask_path

def image(path, costs):
    x_low = min(costs.keys())
    x_high = max(costs.keys())
    xs = [costs.get(i) for i in range(x_low, x_high + 1)]
    ys = [i for i in range(x_low, x_high + 1)]
    sns.set(font_scale=3)
    sns.set_style('white')
    g = sns.barplot(ys, xs, palette=['grey'] * x_high)
    g.axes.yaxis.set_ticklabels([])
    g.margins(y=0, x=0)
    sns.despine(left=True, bottom=True)
    plt.savefig(path, transparent=True, pad_inches=0, bbox_inches='tight')
    return path
