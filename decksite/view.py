import html
from collections import Counter
from typing import List, Optional

import inflect
from anytree.iterators import PreOrderIter
from flask import request, session, url_for
from flask_babel import gettext, ngettext
from mypy_extensions import TypedDict
from werkzeug.routing import BuildError

from decksite import APP, get_season_id
from decksite.data import archetype
from magic import legality, oracle, rotation, tournaments
from magic.models.card import Card
from magic.models.deck import Deck
from shared import dtutil
from shared_web.base_view import BaseView

SeasonInfoDescription = TypedDict('SeasonInfoDescription', {
    'name': str,
    'code': str,
    'code_lower': str,
    'num': Optional[int],
    'url': str,
    'decks_url': str,
    'league_decks_url': str,
    'competitions_url': str,
    'archetypes_url': str,
    'people_url': str,
    'cards_url': str,
    'rotation_changes_url': str,
})

NUM_MOST_COMMON_CARDS_TO_LIST = 10

# pylint: disable=no-self-use, too-many-instance-attributes, too-many-public-methods
class View(BaseView):
    def __init__(self) -> None:
        self.decks: List[Deck] = []
        self.show_active_runs_text: bool = True
        self.active_runs_text: Optional[str] = None
        self.is_very_large: Optional[bool] = None
        self.show_seasons: bool = False
        self.legal_formats: Optional[List[str]] = None
        self.cardhoarder_logo_url = url_for('static', filename='images/cardhoarder.png')
        self.mtgotraders_logo_url = url_for('static', filename='images/mtgotraders.png')

    def season_name(self) -> str:
        return rotation.season_name(get_season_id())

    def season_code_lower(self) -> str:
        return rotation.season_code(get_season_id()).lower()

    def all_seasons(self) -> List[SeasonInfoDescription]:
        seasons: List[SeasonInfoDescription] = [{
            'name': 'All Time',
            'code': 'all',
            'code_lower': 'all',
            'num': None,
            'url': seasonized_url('all'),
            'decks_url': url_for('seasons.season', season_id='all'),
            'league_decks_url': url_for('seasons.season', season_id='all', deck_type='league'),
            'competitions_url': url_for('seasons.competitions', season_id='all'),
            'archetypes_url': url_for('seasons.archetypes', season_id='all'),
            'people_url': url_for('seasons.people', season_id='all'),
            'cards_url': url_for('seasons.cards', season_id='all'),
            'rotation_changes_url': url_for('seasons.rotation_changes', season_id='all')
        }]
        num = 1
        next_rotation_set_code = rotation.next_rotation_ex()['code']
        for code in rotation.SEASONS:
            if code == next_rotation_set_code:
                break
            seasons.append({
                'name': rotation.season_name(num),
                'code': code,
                'code_lower': code.lower(),
                'num': num,
                'url': seasonized_url(num),
                'decks_url': url_for('seasons.season', season_id=num),
                'league_decks_url': url_for('seasons.season', season_id=num, deck_type='league'),
                'competitions_url': url_for('seasons.competitions', season_id=num),
                'archetypes_url': url_for('seasons.archetypes', season_id=num),
                'people_url': url_for('seasons.people', season_id=num),
                'cards_url': url_for('seasons.cards', season_id=num),
                'rotation_changes_url': url_for('seasons.rotation_changes', season_id=num)
            })
            num += 1
        seasons.reverse()
        return seasons

    def favicon_url(self) -> str:
        return url_for('favicon', rest='.ico')

    def favicon_152_url(self) -> str:
        return url_for('favicon', rest='-152.png')

    def title(self) -> str:
        if not self.page_title():
            return 'pennydreadfulmagic.com'
        if get_season_id() == rotation.current_season_num():
            season = ''
        elif get_season_id() == 'all':
            season = ' - All Time'
        else:
            season = ' - Season {n}'.format(n=get_season_id())
        return '{page_title}{season} – pennydreadfulmagic.com'.format(page_title=self.page_title(), season=season)

    def page_title(self) -> Optional[str]:
        pass

    def num_tournaments(self) -> str:
        return inflect.engine().number_to_words(len(tournaments.all_series_info()))

    def rotation_text(self) -> str:
        return rotation.text()

    def learn_more_url(self) -> str:
        return url_for('about', hide_intro=True)

    def decks_url(self) -> str:
        return url_for('decks')

    def current_league_url(self) -> str:
        return url_for('current_league')

    def league_info_url(self) -> str:
        return url_for('league')

    def league_signup_url(self) -> str:
        return url_for('signup')

    def tournaments_info_url(self) -> str:
        return url_for('tournaments')

    def show_legal_seasons(self) -> bool:
        return get_season_id() == 'all'

    def prepare(self) -> None:
        self.prepare_decks()
        self.prepare_cards()
        self.prepare_competitions()
        self.prepare_people()
        self.prepare_archetypes()
        self.prepare_leaderboards()
        self.prepare_legal_formats()

    def prepare_decks(self) -> None:
        self.is_very_large = self.is_very_large or len(getattr(self, 'decks', [])) > 500
        # The 'list' here is just to get past codacy and is a no-op.
        active_runs = [d for d in list(getattr(self, 'decks', [])) if d.is_in_current_run()]
        if len(active_runs) > 0:
            self.active_runs_text = ngettext('%(num)d active league run', '%(num)d active league runs', len(active_runs))
            self.decks = [d for d in self.decks if not d.is_in_current_run()]
        for d in getattr(self, 'decks', []):
            self.prepare_deck(d)

    def prepare_deck(self, d: Deck) -> None:
        set_stars_and_top8(d)
        if d.get('colors') is not None:
            d.colors_safe = colors_html(d.colors, d.colored_symbols)
        d.person_url = '/people/{id}/'.format(id=d.person_id)
        d.date_sort = dtutil.dt2ts(d.active_date)
        d.display_date = dtutil.display_date(d.active_date)
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
        d.comp_row_len = len('{comp_name} (Piloted by {person}'.format(comp_name=d.competition_name, person=d.person))
        if d.get('archetype_id', None):
            d.archetype_url = '/archetypes/{id}/'.format(id=d.archetype_id)
        if d.get('omw') is not None:
            d.omw = str(int(d.omw)) + '%'
        else:
            d.omw = ''
        d.has_legal_format = len(d.legal_formats) > 0
        d.pd_legal = 'Penny Dreadful' in d.legal_formats
        d.legal_icons = ''
        sets = rotation.SEASONS
        if 'Penny Dreadful' in d.legal_formats:
            icon = rotation.current_season_code().lower()
            n = sets.index(icon.upper()) + 1
            d.legal_icons += '<a href="{url}"><i class="ss ss-{code} ss-rare ss-grad">S{n}</i></a>'.format(url='/seasons/{id}/'.format(id=n), code=icon, n=n)
        past_pd_formats = [fmt.replace('Penny Dreadful ', '') for fmt in d.legal_formats if 'Penny Dreadful ' in fmt]
        past_pd_formats.sort(key=lambda code: -sets.index(code))
        for code in past_pd_formats:
            n = sets.index(code.upper()) + 1
            d.legal_icons += '<a href="{url}"><i class="ss ss-{set} ss-common ss-grad">S{n}</i></a>'.format(url='/seasons/{id}/'.format(id=n), set=code.lower(), n=n)
        if 'Commander' in d.legal_formats: # I think C16 looks the nicest.
            d.legal_icons += '<i class="ss ss-c16 ss-uncommon ss-grad">CMDR</i>'
        if session.get('admin') or session.get('demimod') or not d.is_in_current_run():
            d.decklist = str(d).replace('\n', '<br>')
        else:
            d.decklist = ''
        total, num_cards = 0, 0
        for c in d.maindeck:
            if 'Land' not in c.card.type:
                num_cards += c['n']
                total += c['n'] * c.card.cmc
        d.average_cmc = round(total / max(1, num_cards), 2)

    def prepare_cards(self) -> None:
        self.is_very_large = self.is_very_large or len(getattr(self, 'cards', [])) > 500
        for c in getattr(self, 'cards', []):
            self.prepare_card(c)
        for c in getattr(self, 'only_played_cards', []):
            self.prepare_card(c)

    def prepare_card(self, c: Card) -> None:
        c.url = '/cards/{id}/'.format(id=c.name)
        c.img_url = url_for('image', c=c.name)
        c.card_img_class = 'two-faces' if c.layout in ['double-faced', 'meld'] else ''
        c.pd_legal = c.legalities.get('Penny Dreadful', False) and c.legalities['Penny Dreadful'] != 'Banned'
        c.legal_formats = {k for k, v in c.legalities.items() if v != 'Banned'}
        c.has_legal_format = len(c.legal_formats) > 0
        if c.get('all_num_decks') is not None:
            c.all_show_record = c.get('all_wins') or c.get('all_losses') or c.get('all_draws')
        c.has_decks = len(c.get('decks', [])) > 0
        counter = Counter() # type: ignore
        for d in c.get('decks', []):
            for c2 in d.maindeck:
                if not c2.card.type.startswith('Basic Land') and not c2['name'] == c.name:
                    counter[c2['name']] += c2['n']
        most_common_cards = counter.most_common(NUM_MOST_COMMON_CARDS_TO_LIST)
        c.most_common_cards = []
        cs = oracle.cards_by_name()
        for v in most_common_cards:
            self.prepare_card(cs[v[0]])
            c.most_common_cards.append(cs[v[0]])
        c.has_most_common_cards = len(c.most_common_cards) > 0

    def prepare_competitions(self) -> None:
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

    def prepare_people(self) -> None:
        for p in getattr(self, 'people', []):
            p.url = '/people/{id}/'.format(id=p.id)
            p.all_show_record = p.get('all_wins', None) or p.get('all_losses', None) or p.get('all_draws', None)

    def prepare_archetypes(self) -> None:
        for a in getattr(self, 'archetypes', []):
            self.prepare_archetype(a, getattr(self, 'archetypes', []))

    def prepare_archetype(self,
                          a: archetype.Archetype,
                          archetypes: List[archetype.Archetype]
                         ) -> None:
        a.current = a.id == getattr(self, 'archetype', {}).get('id', None)
        if a.get('all_num_decks') is not None:
            a.all_show_record = a.get('all_wins') or a.get('all_draws') or a.get('all_losses')
            a.show_matchups = a.all_show_record
        a.url = '/archetypes/{id}/'.format(id=a.id)
        counter = Counter() # type: ignore
        a.cards = []
        a.most_common_cards = []
        for d in a.get('decks', []):
            a.cards += d.maindeck + d.sideboard
            for c in d.maindeck:
                if not c.card.type.startswith('Basic Land'):
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
            r['url'] = url_for('.archetype', archetype_id=r['id'])
            # It perplexes me that this is necessary. It's something to do with the way NodeMixin magic works. Mustache doesn't like it.
            r['depth'] = r.depth

    def prepare_leaderboards(self) -> None:
        for l in getattr(self, 'leaderboards', []):
            self.prepare_leaderboard(l)

    def prepare_leaderboard(self, leaderboard) -> None:
        pos = 1
        for p in leaderboard:
            p.finish = pos
            if pos <= 8:
                p.position = chr(9311 + pos) # ①, ②, ③, …
            p.url = url_for('.person', person_id=p.person_id)
            pos += 1

    def prepare_legal_formats(self) -> None:
        if getattr(self, 'legal_formats', None) is not None:
            self.legal_formats = list(map(add_season_num, list(sorted(self.legal_formats, key=legality.order_score)))) # type: ignore

    def babel_languages(self):
        return APP.babel.list_translations()

    def TT_HELP_TRANSLATE(self) -> str:
        return gettext('Help us translate the site into your language')

def colors_html(colors: List[str], colored_symbols: List[str]) -> str:
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

def set_stars_and_top8(d: Deck) -> None:
    if d.finish == 1 and d.competition_top_n >= 1:
        d.top8_safe = '<span title="Winner">①</span>'
        d.stars_safe = '★★★'
    elif d.finish == 2 and d.competition_top_n >= 2:
        d.top8_safe = '<span title="Losing Finalist">②</span>'
        d.stars_safe = '★★'
    elif d.finish == 3 and d.competition_top_n >= 3:
        d.top8_safe = '<span title="Losing Semifinalist">④</span>'
        d.stars_safe = '★★'
    elif d.finish == 5 and d.competition_top_n >= 5:
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

def seasonized_url(season_id) -> str:
    args = request.view_args.copy()
    if season_id == rotation.current_season_num():
        args.pop('season_id', None)
        endpoint = request.endpoint.replace('seasons.', '')
    else:
        args['season_id'] = season_id
        prefix = '' if request.endpoint.startswith('seasons.') else 'seasons.'
        endpoint = '{prefix}{endpoint}'.format(prefix=prefix, endpoint=request.endpoint)
    try:
        return url_for(endpoint, **args)
    except BuildError:
        return url_for(request.endpoint)

def add_season_num(f):
    if not 'Penny Dreadful ' in f:
        return f
    code = f.replace('Penny Dreadful ', '')
    num = rotation.season_num(code)
    return f.replace(code, f'{code} (Season {num})')
