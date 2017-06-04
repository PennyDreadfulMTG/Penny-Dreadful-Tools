import os.path

import matplotlib.pyplot as plt
import seaborn as sns

from decksite.data import deck
from shared import configuration

def cmc(deck_id):
    name = str(deck_id) + '-cmc.png'
    path = configuration.get('image_dir') + '/' + name
    if os.path.exists(path):
        return path
    d = deck.load_deck(deck_id)
    costs = {}
    for ci in d.maindeck:
        if not ci.get('card').is_land():
            # The 0 here is a bit of a hack because it's wrong for split cards. But we should convert CMC to be a single value not a list from now on.
            cost = int(float(ci.get('card').cmc[0])) # Invalid for Unglued half costs.
            costs[cost] = ci.get('n') + costs.get(cost, 0)
    return image(path, costs)

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
