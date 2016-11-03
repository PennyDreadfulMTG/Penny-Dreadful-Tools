import html
import re
import urllib

from flask import url_for

from magic import mana, legality
from shared import dtutil

from decksite import deck_name
from decksite import template

NAME_MAX_LEN = 35

# pylint: disable=no-self-use
class View:
    def template(self):
        return self.__class__.__name__.lower()

    def content(self):
        return template.render(self)

    def page(self):
        return template.render_name('page', self)

    def home_url(self):
        return url_for('home')

    def css_url(self):
        return url_for('static', filename='css/pd.css')

    def tooltips_url(self):
        return url_for('static', filename='js/tooltips.js')

    def js_url(self):
        return url_for('static', filename='js/pd.js')

    def menu(self):
        return [
            {'name': 'Decks', 'url': url_for('home')},
            {'name': 'Competitions', 'url': url_for('competitions')},
            {'name': 'People', 'url': url_for('people')},
            {'name': 'Cards', 'url': url_for('cards')},
            {'name': 'About', 'url': url_for('about')},
        ]

    def favicon_url(self):
        return url_for('favicon', rest='.ico')

    def favicon_152_url(self):
        return url_for('favicon', rest='-152.png')

    def title(self):
        if not self.subtitle():
            return 'Penny Dreadful Decks'
        else:
            return '{subtitle} – Penny Dreadful Decks'.format(subtitle=self.subtitle())

    def subtitle(self):
        return None

    def prepare(self):
        self.prepare_decks()
        self.prepare_cards()
        self.prepare_competitions()
        self.prepare_people()

    def prepare_decks(self):
        for d in getattr(self, 'decks', []):
            set_stars_and_top8(d)
            d.colors_safe = colors_html(d.colors)
            name = deck_name.normalize(d)
            d.name = name[0:NAME_MAX_LEN - 1] + '…' if len(name) > NAME_MAX_LEN else name
            d.person_url = url_for('person', person_id=d.person_id)
            d.date_sort = dtutil.dt2ts(d.date)
            d.display_date = dtutil.display_date(d.date)
            d.show_record = d.wins or d.losses
            d.players = d.players if d.players > 0 else ''
            if d.competition_id:
                d.competition_url = url_for('competition', competition_id=d.competition_id)
            d.url = url_for('decks', deck_id=self.id)

    def prepare_cards(self):
        cards = getattr(self, 'cards', [])
        legal = legality.legality(cards)
        for c in cards:
            c.url = url_for('card', name=c.name)
            c.img_url = 'http://magic.bluebones.net/proxies/?c={name}'.format(name=urllib.parse.quote(c.name))
            c.pd_legal = legal[c.id]

    def prepare_competitions(self):
        for c in getattr(self, 'competitions', []):
            c.url = url_for('competition', competition_id=c.id)
            c.display_date = dtutil.display_date(c.start_date)

    def prepare_people(self):
        for p in getattr(self, 'people', []):
            p.url = url_for('person', person_id=p.id)
            p.show_record = p.wins or p.losses

def colors_html(colors):
    s = ''.join(mana.order(colors))
    n = len(colors)
    return re.sub('([WUBRG])', r'<span class="mana mana-{n} mana-\1"></span>'.format(n=n), html.escape(s))

def set_stars_and_top8(d):
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
        if d.get('wins') and d.get('losses'):
            if d.wins - 5 >= d.losses:
                d.stars = '★★'
            elif d.wins - 3 >= d.losses:
                d.stars = '★'
            else:
                d.stars = ''
        else:
            d.stars = ''
