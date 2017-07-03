import subprocess
import urllib
from collections import Counter

from flask import url_for
from munch import Munch

from magic import oracle
from shared import dtutil

from decksite import deck_name
from decksite import template
from decksite import league

# pylint: disable=no-self-use, too-many-public-methods
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
        return url_for('static', filename='css/pd.css', v=self.commit_id())

    def tooltips_url(self):
        return url_for('static', filename='js/tooltips.js', v=self.commit_id())

    def js_url(self):
        return url_for('static', filename='js/pd.js', v=self.commit_id())

    def menu(self):
        return [
            {'name': 'Decks', 'url': url_for('home')},
            {'name': 'Competitions', 'url': url_for('competitions')},
            {'name': 'People', 'url': url_for('people')},
            {'name': 'Cards', 'url': url_for('cards')},
            {'name': 'Archetypes', 'url': url_for('archetypes')},
            {'name': 'Resources', 'url': url_for('resources')},
            {'name': 'About', 'url': url_for('about')},
            {'name': 'League', 'url': url_for('league'), 'has_submenu': True, 'submenu': [
                {'name': 'Sign Up', 'url': url_for('signup')},
                {'name': 'Report', 'url': url_for('report')},
                {'name': 'Records', 'url': url_for('competition', competition_id=league.get_active_competition_id())},
            ]}
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
        self.prepare_archetypes()

    def prepare_decks(self):
        for d in getattr(self, 'decks', []):
            self.prepare_deck(d)
        for d in getattr(self, 'similar', []):
            self.prepare_deck(d)

    def prepare_deck(self, d):
        set_stars_and_top8(d)
        if d.get('colors', None):
            d.colors_safe = colors_html(d.colors, d.colored_symbols)
            d.name = deck_name.normalize(d)
        d.person_url = url_for('person', person_id=d.person_id)
        d.date_sort = dtutil.dt2ts(d.date)
        d.display_date = dtutil.display_date(d.date)
        d.show_record = d.wins or d.losses or d.draws
        if d.competition_id:
            d.competition_url = url_for('competition', competition_id=d.competition_id)
        d.url = url_for('decks', deck_id=d.id)
        d.export_url = url_for('export', deck_id=d.id)
        d.cmc_chart_url = url_for('cmc_chart', deck_id=d.id)
        if d.source_name == 'League':
            d.source_indicator = 'League'
            if d.wins + d.losses < 5 and d.competition_end_date > dtutil.now() and not d.get('retired', False):
                d.stars = '⊕ {stars}'.format(stars=d.stars).strip()
                d.source_sort = '1'
        elif d.source_name == 'Gatherling':
            d.source_indicator = 'Gatherling'
        elif d.source_name == 'Tapped Out':
            d.source_indicator = 'Tapped Out'
        d.comp_row_len = len("{comp_name} (Piloted by {person}".format(comp_name=d.competition_name, person=d.person))
        if d.get('archetype_id', None):
            d.archetype_url = url_for('archetype', archetype_id=d.archetype_id)
        if d.omw is not None:
            d.omw = str(int(d.omw)) + '%'
        else:
            d.omw = ''

    def prepare_cards(self):
        for c in getattr(self, 'cards', []):
            self.prepare_card(c)
        for c in getattr(self, 'only_played_cards', []):
            self.prepare_card(c)

    def prepare_card(self, c):
        c.url = url_for('card', name=c.name)
        c.img_url = 'http://magic.bluebones.net/proxies/?c={name}'.format(name=urllib.parse.quote(c.name))
        c.img_url = 'https://deckbox.org/mtg/' + c.name + '/tooltip'
        c.pd_legal = c.legalities.get('Penny Dreadful', False)
        c.legal_formats = c.legalities.keys()
        c.has_legal_format = len(c.legal_formats) > 0
        c.show_record_season = c.get('wins_season') or c.get('losses_season') or c.get('draws_season')
        c.show_record_all = c.get('wins_all') or c.get('losses_all') or c.get('draws_all')
        c.has_decks = len(c.get('decks', [])) > 0

    def prepare_competitions(self):
        for c in getattr(self, 'competitions', []):
            c.competition_url = url_for('competition', competition_id=c.id)
            c.display_date = dtutil.display_date(c.start_date)
            c.ends = '' if c.end_date < dtutil.now() else dtutil.display_date(c.end_date)
            c.date_sort = dtutil.dt2ts(c.start_date)

    def prepare_people(self):
        for p in getattr(self, 'people', []):
            p.url = url_for('person', person_id=p.id)
            p.show_record_season = p.wins_season or p.losses_season or p.get('draws_season', None)
            p.show_record = p.wins or p.losses or p.get('draws', None)

    def prepare_archetypes(self):
        num_most_common_cards_to_list = 10
        for a in getattr(self, 'archetypes', []):
            a.url = url_for('archetype', archetype_id=a.id)
            a.best_decks = Munch({'decks': []})
            n = 3
            while len(a.best_decks.decks) == 0 and n >= 0:
                for d in a.decks:
                    if len(d.get('stars', '')) >= n:
                        a.best_decks.decks.append(d)
                n -= 1
            counter = Counter()
            a.cards = []
            a.most_common_cards = []
            for d in a.decks:
                a.cards += d.maindeck + d.sideboard
                for c in d.maindeck:
                    if not c['card'].type.startswith('Basic Land'):
                        counter[c['name']] += c['n']
            most_common_cards = counter.most_common(num_most_common_cards_to_list)
            cs = {c.name: c for c in oracle.load_cards()}
            for v in most_common_cards:
                a.most_common_cards.append(cs[v[0]])
            a.archetype_tree = preorder(a.tree)
            lowest = a.tree['pos']
            for r in a.archetype_tree:
                r['url'] = url_for('archetype', archetype_id=r['id'])
                r['padding'] = '&nbsp;' * 4 * (r['pos'] - lowest)

    def commit_id(self):
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'])


def preorder(node):
    result = []
    result.append(node)
    for child in node.get('children', []):
        result += preorder(child)
    return result

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
