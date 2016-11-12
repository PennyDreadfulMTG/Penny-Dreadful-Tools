import urllib

from flask import url_for

from shared import dtutil

from decksite import deck_name
from decksite import template

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
            {'name': 'Resources', 'url': url_for('resources')},
            {'name': 'Sign Up', 'url': url_for('signup')},
            {'name': 'Report', 'url': url_for('report')},
            {'name': 'About', 'url': url_for('about')}
        ]

    def favicon_url(self):
        return url_for('favicon', rest='.ico')

    def favicon_152_url(self):
        return url_for('favicon', rest='-152.png')

    def title(self):
        if not self.subtitle():
            return 'pennydreadfulmagic.com'
        else:
            return '{subtitle} – pennydreadfulmagic.com'.format(subtitle=self.subtitle())

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
            d.colors_safe = colors_html(d.colors, d.colored_symbols)
            d.name = deck_name.normalize(d)
            d.person_url = url_for('person', person_id=d.person_id)
            d.date_sort = dtutil.dt2ts(d.date)
            d.display_date = dtutil.display_date(d.date)
            d.show_record = d.wins or d.losses or d.draws
            d.players = d.players if d.players > 0 else ''
            if d.competition_id:
                d.competition_url = url_for('competition', competition_id=d.competition_id)
            d.url = url_for('decks', deck_id=d.id)
            d.export_url = url_for('export', deck_id=d.id)
            if d.source_name == 'League':
                d.source_indicator = 'League'
                if d.wins + d.losses < 5 and d.competition_end_date > dtutil.now():
                    d.stars = '⊕ {stars}'.format(stars=d.stars).strip()
                    d.source_sort = '1'
            elif d.source_name == 'Gatherling':
                d.source_indicator = 'Gatherling'
            elif d.source_name == 'Tapped Out':
                d.source_indicator = 'Tapped Out'

    def prepare_cards(self):
        cards = getattr(self, 'cards', [])
        for c in cards:
            c.url = url_for('card', name=c.name)
            c.img_url = 'http://magic.bluebones.net/proxies/?c={name}'.format(name=urllib.parse.quote(c.name))
            c.pd_legal = c.legalities.get('Penny Dreadful', False)
            c.legal_formats = c.legalities.keys()
            c.has_legal_format = len(c.legal_formats) > 0
            c.show_record = c.wins or c.losses or c.draws

    def prepare_competitions(self):
        for c in getattr(self, 'competitions', []):
            c.competition_url = url_for('competition', competition_id=c.id)
            c.display_date = dtutil.display_date(c.start_date)
            c.date_sort = dtutil.dt2ts(c.start_date)

    def prepare_people(self):
        for p in getattr(self, 'people', []):
            p.url = url_for('person', person_id=p.id)
            p.show_record = p.wins or p.losses or p.draws

def colors_html(colors, colored_symbols):
    s = ''
    total = len(colored_symbols)
    for color in colors:
        n = colored_symbols.count(color)
        width = (3.0 - 0.1 * len(colors)) / total * n
        s += '<span class="mana mana-{color}" style="width: {width}rem"></span>'.format(color=color, width=width)
    return s


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
        if d.get('wins') is not None and d.get('losses') is not None:
            if d.wins - 5 >= d.losses:
                d.stars = '★★'
            elif d.wins - 3 >= d.losses:
                d.stars = '★'
            else:
                d.stars = ''
        else:
            d.stars = ''
