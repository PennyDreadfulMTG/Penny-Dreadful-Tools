import datetime
import html
import urllib
from collections import Counter

from anytree.iterators import PreOrderIter
from flask import request, session, url_for
from flask_babel import gettext

from decksite import APP, BABEL, template
from decksite.data import archetype, deck
from magic import multiverse, oracle, rotation
from shared import dtutil
from shared.container import Container

NUM_MOST_COMMON_CARDS_TO_LIST = 10

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
        # Don't preload 10,000 images.
        # pylint: disable=no-member
        if not hasattr(self, 'cards') or len(self.cards) > 500:
            return None
        return url_for('static', filename='js/tooltips.js', v=self.commit_id())

    def js_url(self):
        return url_for('static', filename='js/pd.js', v=self.commit_id())

    def menu(self):
        archetypes_badge = None
        if session.get('admin') is True:
            n = len(deck.load_decks('NOT d.reviewed'))
            if n > 0:
                archetypes_badge = {'url': url_for('edit_archetypes'), 'text': n}
        rotation_submenu = []
        if (rotation.next_rotation() - dtutil.now()) < datetime.timedelta(7) or (rotation.next_supplemental() - dtutil.now()) < datetime.timedelta(7):
            rotation_submenu += [{'name': gettext('Rotation Tracking'), 'url': url_for('rotation')}]
        rotation_submenu += [
            {'name': gettext('Rotation Changes'), 'url': url_for('rotation_changes')},
            {'name': gettext('Rotation Speculation'), 'url': url_for('rotation_speculation')},
            {'name': gettext('External Links'), 'url': url_for('resources')},
        ]
        if session.get('id'):
            rotation_submenu += [
                {'name': gettext('Log Out'), 'url': url_for('logout')}
            ]
        else:
            rotation_submenu += [
                {'name': gettext('Log In'), 'url': url_for('authenticate', target=request.url)}
            ]

        menu = [
            {'name': gettext('Metagame'), 'url': url_for('home'), 'badge': archetypes_badge, 'submenu': [
                {'name': gettext('Latest Decks'), 'url': url_for('decks')},
                {'name': gettext('Archetypes'), 'url': url_for('archetypes'), 'badge': archetypes_badge},
                {'name': gettext('People'), 'url': url_for('people')},
                {'name': gettext('Cards'), 'url': url_for('cards')},
                {'name': gettext('Past Seasons'), 'url': url_for('seasons')}
            ]},
            {'name': gettext('League'), 'url': url_for('league'), 'submenu': [
                {'name': gettext('League Info'), 'url': url_for('league')},
                {'name': gettext('Sign Up'), 'url': url_for('signup')},
                {'name': gettext('Report'), 'url': url_for('report')},
                {'name': gettext('Records'), 'url': url_for('current_league')},
                {'name': gettext('Retire'), 'url': url_for('retire')},
            ]},
            {'name': gettext('Competitions'), 'url': url_for('competitions'), 'submenu': [
                {'name': gettext('Competition Results'), 'url': url_for('competitions')},
                {'name': gettext('Tournament Info'), 'url': url_for('tournaments')},
                {'name': gettext('Leaderboards'), 'url': url_for('tournament_leaderboards')},
                {'name': gettext('Gatherling'), 'url': 'https://gatherling.com/'},
                {'name': gettext('Hosting'), 'url': url_for('hosting')}
            ]},
            {'name': gettext('Resources'), 'url': url_for('resources'), 'submenu': rotation_submenu},
            {'name': gettext('About'), 'url': url_for('about'), 'submenu': [
                {'name': gettext('What is Penny Dreadful?'), 'url': url_for('about')},
                {'name': gettext('About pennydreadfulmagic.com'), 'url': url_for('about_pdm')}
            ]}
        ]
        for item in menu:
            item['has_submenu'] = item.get('submenu') is not None
            item['is_external'] = item.get('url', '').startswith('http') and '://pennydreadfulmagic.com/' not in item['url']
            for subitem in item.get('submenu', []):
                subitem['is_external'] = subitem.get('url', '').startswith('http') and '://pennydreadfulmagic.com/' not in subitem['url']
        return menu

    def favicon_url(self):
        return url_for('favicon', rest='.ico')

    def favicon_152_url(self):
        return url_for('favicon', rest='-152.png')

    def title(self):
        if not self.subtitle():
            return 'pennydreadfulmagic.com'
        return '{subtitle} – pennydreadfulmagic.com'.format(subtitle=self.subtitle())

    def subtitle(self):
        return None

    def prepare(self):
        self.prepare_decks()
        self.prepare_cards()
        self.prepare_competitions()
        self.prepare_people()
        self.prepare_archetypes()
        self.prepare_leaderboards()

    def prepare_decks(self):
        for d in getattr(self, 'decks', []):
            self.prepare_deck(d)
        for d in getattr(self, 'similar', []):
            self.prepare_deck(d)

    def prepare_deck(self, d):
        set_stars_and_top8(d)
        if d.get('colors') is not None:
            d.colors_safe = colors_html(d.colors, d.colored_symbols)
        d.person_url = '/people/{id}/'.format(id=d.person_id)
        d.date_sort = dtutil.dt2ts(d.date)
        d.display_date = dtutil.display_date(d.date)
        d.show_record = d.wins or d.losses or d.draws
        if d.competition_id:
            d.competition_url = '/competitions/{id}/'.format(id=d.competition_id)
        d.url = '/decks/{id}/'.format(id=d.id)
        d.export_url = '/export/{id}/'.format(id=d.id)
        d.cmc_chart_url = '/charts/cmc/{id}-cmc.png'.format(id=d.id)
        if d.is_in_current_run():
            d.active_safe = '<span class="active" title="Active in the current league">⊕</span>'
            d.stars_safe = '{active} {stars}'.format(active=d.active_safe, stars=d.stars_safe).strip()
            d.source_sort = '1'
        d.source_is_external = False if d.source_name == 'League' else True
        d.comp_row_len = len("{comp_name} (Piloted by {person}".format(comp_name=d.competition_name, person=d.person))
        if d.get('archetype_id', None):
            d.archetype_url = '/archetypes/{id}/'.format(id=d.archetype_id)
        if d.get('omw') is not None:
            d.omw = str(int(d.omw)) + '%'
        else:
            d.omw = ''
        d.has_legal_format = len(d.legal_formats) > 0
        d.pd_legal = 'Penny Dreadful' in d.legal_formats
        d.legal_icons = ''
        sets = multiverse.SEASONS
        if 'Penny Dreadful' in d.legal_formats:
            icon = rotation.last_rotation_ex()['code'].lower()
            n = sets.index(icon.upper()) + 1
            d.legal_icons += '<a href="{url}"><i class="ss ss-{code} ss-rare ss-grad">S{n}</i></a>'.format(url='/seasons/{id}/'.format(id=n), code=icon, n=n)
        past_pd_formats = [fmt.replace('Penny Dreadful ', '') for fmt in d.legal_formats if 'Penny Dreadful ' in fmt]
        past_pd_formats.sort(key=lambda code: -sets.index(code))
        for code in past_pd_formats:
            n = sets.index(code.upper()) + 1
            d.legal_icons += '<a href="{url}"><i class="ss ss-{set} ss-common ss-grad">S{n}</i></a>'.format(url='/seasons/{id}/'.format(id=n), set=code.lower(), n=n)
        if 'Commander' in d.legal_formats: # I think C16 looks the nicest.
            d.legal_icons += '<i class="ss ss-c16 ss-uncommon ss-grad">CMDR</i>'
        if session.get('admin') or not d.is_in_current_run():
            d.decklist = str(d).replace('\n', '<br>')
        else:
            d.decklist = ''
        total, num_cards = 0, 0
        for c in d.maindeck:
            if 'Land' not in c['card'].type:
                num_cards += c['n']
                total += c['n'] * c['card'].cmc
        d.average_cmc = round(total / max(1, num_cards), 2)

    def prepare_cards(self):
        for c in getattr(self, 'cards', []):
            self.prepare_card(c)
        for c in getattr(self, 'only_played_cards', []):
            self.prepare_card(c)

    def prepare_card(self, c):
        c.url = '/cards/{id}/'.format(id=c.name)
        c.img_url = 'http://magic.bluebones.net/proxies/index2.php?c={name}'.format(name=urllib.parse.quote(c.name))
        c.card_img_class = 'two-faces' if c.layout in ['double-faced', 'meld'] else ''
        c.pd_legal = c.legalities.get('Penny Dreadful', False) and c.legalities['Penny Dreadful'] != 'Banned'
        c.legal_formats = set([k for k, v in c.legalities.items() if v != 'Banned'])
        c.has_legal_format = len(c.legal_formats) > 0
        if c.get('season_num_decks') is not None and c.get('all_num_decks') is not None:
            c.season_show_record = c.get('season_wins') or c.get('season_losses') or c.get('season_draws')
            c.all_show_record = c.get('all_wins') or c.get('all_losses') or c.get('all_draws')
        c.has_decks = len(c.get('decks', [])) > 0
        counter = Counter()
        for d in c.get('decks', []):
            for c2 in d.maindeck:
                if not c2['card'].type.startswith('Basic Land') and not c2['name'] == c.name:
                    counter[c2['name']] += c2['n']
        most_common_cards = counter.most_common(NUM_MOST_COMMON_CARDS_TO_LIST)
        c.most_common_cards = []
        cs = oracle.cards_by_name()
        for v in most_common_cards:
            self.prepare_card(cs[v[0]])
            c.most_common_cards.append(cs[v[0]])
        c.has_most_common_cards = len(c.most_common_cards) > 0

    def prepare_competitions(self):
        for c in getattr(self, 'competitions', []):
            c.competition_url = '/competitions/{id}/'.format(id=c.id)
            c.display_date = dtutil.display_date(c.start_date)
            c.ends = '' if c.end_date < dtutil.now() else dtutil.display_date(c.end_date)
            c.date_sort = dtutil.dt2ts(c.start_date)
            c.league = True if c.type == 'League' else False
            title_safe = ''
            try:
                for k, v in c.base_archetypes_data().items():
                    if v > 0:
                        title_safe += '{v} {k}<br>'.format(v=v, k=html.escape(k))
            except KeyError:
                archetype.rebuild_archetypes()
            c.archetypes_sparkline_chart_title_safe = title_safe
            c.archetypes_sparkline_chart_url = url_for('archetype_sparkline_chart', competition_id=c.id)

    def prepare_people(self):
        for p in getattr(self, 'people', []):
            p.url = '/people/{id}/'.format(id=p.id)
            if p.get('season_num_decks') is not None and p.get('all_num_decks') is not None:
                p.season_show_record = p.season_wins or p.season_losses or p.get('season_draws', None)
                p.all_show_record = p.all_wins or p.all_losses or p.get('all_draws', None)

    def prepare_archetypes(self):
        for a in getattr(self, 'archetypes', []):
            self.prepare_archetype(a, getattr(self, 'archetypes', []))

    def prepare_archetype(self, a, archetypes):
        a.current = a.id == getattr(self, 'archetype', {}).get('id', None)
        if a.get('all_num_decks') is not None and a.get('season_num_decks') is not None:
            a.all_show_record = a.get('all_wins') or a.get('all_draws') or a.get('all_losses')
            a.season_show_record = a.get('season_wins') or a.get('season_draws') or a.get('season_losses')
            a.show_matchups = a.all_show_record
        a.url = '/archetypes/{id}/'.format(id=a.id)
        a.best_decks = Container({'decks': []})
        n = 3
        while len(a.best_decks.decks) == 0 and n >= 0:
            for d in a.get('decks', []):
                if d.get('stars_safe', '').count('★') >= n:
                    a.best_decks.decks.append(d)
            n -= 1
        a.show_best_decks = len(a.decks) != len(a.best_decks.decks)
        counter = Counter()
        a.cards = []
        a.most_common_cards = []
        for d in a.get('decks', []):
            a.cards += d.maindeck + d.sideboard
            for c in d.maindeck:
                if not c['card'].type.startswith('Basic Land'):
                    counter[c['name']] += c['n']
        most_common_cards = counter.most_common(NUM_MOST_COMMON_CARDS_TO_LIST)
        cs = oracle.cards_by_name()
        for v in most_common_cards:
            self.prepare_card(cs[v[0]])
            a.most_common_cards.append(cs[v[0]])
        a.has_most_common_cards = len(a.most_common_cards) > 0
        a.archetype_tree = PreOrderIter(a)
        for r in a.archetype_tree:
            # Prune branches we don't want to show
            if r.id not in [a.id for a in archetypes]:
                r.parent = None
            r['url'] = '/archetypes/{id}/'.format(id=r['id'])
            # It perplexes me that this is necessary. It's something to do with the way NodeMixin magic works. Mustache doesn't like it.
            r['depth'] = r.depth

    def prepare_leaderboards(self):
        for l in getattr(self, 'leaderboards', []):
            self.prepare_leaderboard(l)

    def prepare_leaderboard(self, leaderboard):
        pos = 1
        for p in leaderboard:
            p.finish = pos
            p.stage_reached = 1
            p.position = chr(9311 + pos) # ①, ②, ③, …
            p.url = url_for('person', person_id=p.person_id)
            pos += 1
            if pos > 8:
                break

    def commit_id(self):
        return APP.config['commit-id']

    def babel_languages(self):
        return BABEL.list_translations()

    def language_icon(self):
        return url_for('static', filename='images/language_icon.svg')

    def TT_HELP_TRANSLATE(self) -> str:
        return gettext("Help us translate the site into your language")

def colors_html(colors, colored_symbols):
    total = len(colored_symbols)
    if total == 0:
        return '<span class="mana" style="width: 3rem"></span>'
    s = ''
    for color in colors:
        n = colored_symbols.count(color)
        one_pixel_in_rem = 0.05 # See pd.css base font size for the derivation of this value.
        width = (3.0 - one_pixel_in_rem * len(colors)) / total * n
        s += '<span class="mana mana-{color}" style="width: {width}rem"></span>'.format(color=color, width=width)
    return s

def set_stars_and_top8(d):
    if d.finish == 1:
        d.top8_safe = '<span title="Winner">①</span>'
        d.stars_safe = '★★★'
    elif d.finish == 2:
        d.top8_safe = '<span title="Losing Finalist">②</span>'
        d.stars_safe = '★★'
    elif d.finish == 3:
        d.top8_safe = '<span title="Losing Semifinalist">④</span>'
        d.stars_safe = '★★'
    elif d.finish == 5 and d.get('stage_reached', 0) > 0: # Don't show ⑧ for fifth place in a top 4 tournament.
        d.top8_safe = '<span title="Losing Quarterfinalist">⑧</span>'
        d.stars_safe = '★'
    else:
        d.top8_safe = ''
        if d.get('wins') is not None and d.get('losses') is not None:
            if d.wins - 5 >= d.losses:
                d.stars_safe = '★★'
            elif d.wins - 3 >= d.losses:
                d.stars_safe = '★'
            else:
                d.stars_safe = ''
        else:
            d.stars_safe = ''

    if len(d.stars_safe) > 0:
        d.stars_safe = '<span class="stars" title="Success Rating">{stars}</span>'.format(stars=d.stars_safe)
