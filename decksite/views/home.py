import html
import re

from magic import mana

from decksite import deck_name
from decksite.view import View

NAME_MAX_LEN = 35


# pylint: disable=no-self-use
class Home(View):
    def __init__(self, decks):
        self._decks = decks
        for d in self._decks:
            if d.finish == 1:
                d.top8 = '①'
                d.stars = '★★★'
            elif d.finish == 2:
                d.top8 = '②'
                d.stars = '★★'
            elif d.finish == 3:
                d.top8 = '④'
                d.stars = '★★'
            elif d.finish == 5:
                d.top8 = '⑧'
                d.stars = '★'
            else:
                d.top8 = ''
                if d.wins - 5 >= d.losses:
                    d.stars = '★★'
                elif d.wins - 3 >= d.losses:
                    d.stars = '★'
                else:
                    d.stars = ''
            d.colors_safe = colors_html(d.colors)
            name = deck_name.normalize(d)
            d.name = name[0:NAME_MAX_LEN - 1] + '…' if len(name) > NAME_MAX_LEN else name
            d.person = d.person.lower()

    def decks(self):
        return self._decks

    def subtitle(self):
        return None

def colors_html(colors):
    s = ''.join(mana.order(colors))
    n = len(colors)
    return re.sub('([WUBRG])', r'<span class="mana mana-{n} mana-\1"></span>'.format(n=n), html.escape(s))
