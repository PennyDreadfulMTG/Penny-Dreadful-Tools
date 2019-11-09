import html
from collections import Counter
from typing import Any, List, Optional, Union, cast

import inflect
from anytree.iterators import PreOrderIter
from babel import Locale
from flask import request, url_for
from flask_babel import gettext, ngettext
from mypy_extensions import TypedDict
from werkzeug.routing import BuildError

from decksite import APP, get_season_id, prepare
from decksite.data import archetype, competition
from magic import legality, oracle, rotation, tournaments
from magic.models import Card, Deck
from shared import dtutil
from shared.container import Container
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
        self.active_runs_text: str = ''
        self.hide_active_runs = True
        self.show_seasons: bool = False
        self.legal_formats: Optional[List[str]] = None
        self.cardhoarder_logo_url = url_for('static', filename='images/cardhoarder.png')
        self.mtgotraders_logo_url = url_for('static', filename='images/mtgotraders.png')
        self.is_person_page: Optional[bool] = None
        self._card_image_template: Optional[str] = None
        self._card_url_template: Optional[str] = None

        self.next_tournament_name = None
        self.next_tournament_time = None
        self.tournaments: List[Container] = []
        self.content_class = 'content-' + self.__class__.__name__.lower()
        self.page_size = request.cookies.get('page_size', 20)
        self.tournament_only = False

    def season_id(self) -> int:
        return get_season_id()

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
            'decks_url': url_for('seasons.decks', season_id='all'),
            'league_decks_url': url_for('seasons.decks', season_id='all', deck_type='league'),
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
                'decks_url': url_for('seasons.decks', season_id=num),
                'league_decks_url': url_for('seasons.decks', season_id=num, deck_type='league'),
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
        return rotation.message()

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
        self.prepare_matches()

    def prepare_decks(self) -> None:
        self.prepare_active_runs(self)
        prepare.prepare_decks(getattr(self, 'decks', []))

    def prepare_cards(self) -> None:
        for c in getattr(self, 'cards', []):
            self.prepare_card(c)

    def url_for_image(self, name: str) -> str:
        if self._card_image_template is None:
            self._card_image_template = url_for('image', c='{cardname}')
        return self._card_image_template.format(name=name)

    def url_for_card(self, c: Card) -> str:
        if self._card_url_template is None:
            if self.tournament_only:
                self._card_url_template = url_for('.card_tournament', name='{cardname}')
            else:
                self._card_url_template = url_for('.card', name='{cardname}')
        return self._card_url_template.format(cardname=c.name)

    def prepare_card_urls(self, c: Card) -> None:
        c.url = self.url_for_card(c)
        c.img_url = self.url_for_image(c.name)

    def prepare_card(self, c: Card) -> None:
        self.prepare_card_urls(c)
        c.card_img_class = 'two-faces' if c.layout in ['transform', 'meld'] else ''
        c.pd_legal = c.legalities.get('Penny Dreadful', False) and c.legalities['Penny Dreadful'] != 'Banned'
        c.legal_formats = {k for k, v in c.legalities.items() if v != 'Banned'}
        c.has_legal_format = len(c.legal_formats) > 0
        if c.get('num_decks') is not None:
            c.show_record = c.get('wins') or c.get('losses') or c.get('draws')

        c.has_decks = len(c.get('decks', [])) > 0
        if not c.has_decks:
            c.has_most_common_cards = False
            return

        counter = Counter() # type: ignore
        for d in c.get('decks', []):
            for c2 in d.maindeck:
                if not c2.card.type_line.startswith('Basic Land') and not c2['name'] == c.name:
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
            c.league = c.type == 'League'
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
            p.show_record = p.get('wins', None) or p.get('losses', None) or p.get('draws', None)

    def prepare_archetypes(self) -> None:
        for a in getattr(self, 'archetypes', []):
            self.prepare_archetype(a, getattr(self, 'archetypes', []))

    def prepare_archetype(self, a: archetype.Archetype, archetypes: List[archetype.Archetype]) -> None:

        a.current = a.id == getattr(self, 'archetype', {}).get('id', None)

        a.show_record = a.get('num_decks') is not None and (a.get('wins') or a.get('draws') or a.get('losses'))
        a.show_record_tournament = a.get('num_decks_tournament') is not None and (a.get('wins_tournament') or a.get('draws_tournament') or a.get('losses_tournament'))

        counter = Counter() # type: ignore
        a.cards = []
        a.most_common_cards = []

        counter_tournament = Counter() # type: ignore
        a.cards_tournament = []
        a.most_common_cards_tournament = []

        # Make a pass, collecting card counts for all decks and for tournament decks
        for d in a.get('decks', []):
            a.cards += d.maindeck + d.sideboard
            for c in d.maindeck:
                if not c.card.type_line.startswith('Basic Land'):
                    counter[c['name']] += c['n']
                    if d.competition_type_name == 'Gatherling':
                        counter_tournament[c['name']] += c['n']

        most_common_cards = counter.most_common(NUM_MOST_COMMON_CARDS_TO_LIST)
        most_common_cards_tournament = counter_tournament.most_common(NUM_MOST_COMMON_CARDS_TO_LIST)

        cs = oracle.cards_by_name()

        for v in most_common_cards:
            self.prepare_card(cs[v[0]])
            a.most_common_cards.append(cs[v[0]])
        a.has_most_common_cards = len(a.most_common_cards) > 0

        for v in most_common_cards_tournament:
            self.prepare_card(cs[v[0]])
            a.most_common_cards_tournament.append(cs[v[0]])
        a.has_most_common_cards_tournament = len(a.most_common_cards_tournament) > 0

        # Set up archetype tree, pruning siblings that we don't want to show.
        a.archetype_tree = [r for r in PreOrderIter(a) if r.id in [a.id for a in archetypes]]
        for r in a.archetype_tree:
            r['url'] = url_for('.archetype', archetype_id=r['id'])
            r['url_tournament'] = url_for('.archetype_tournament', archetype_id=r['id'])
            # It perplexes me that this is necessary. It's something to do with the way NodeMixin magic works. Mustache doesn't like it.
            r['depth'] = r.depth

    def prepare_leaderboards(self) -> None:
        for l in getattr(self, 'leaderboards', []):
            self.prepare_leaderboard(l)

    def prepare_leaderboard(self, leaderboard: List[Container]) -> None:
        # each Container in leaderboard is expected to have attributes:
        #   - person_id: the id of the person
        #   - person: the name to display for that person (see data/query.py:person_query)
        #   - score: a value such that two rows are tied if and only if they have the same score
        # leaderboard is expected to be sorted such that leaderboard[0] is winning
        # Depending on the view, the containers may have other attributes as well

        finish = 0
        score = None
        for i, p in enumerate(leaderboard, start=1):
            if finish == 0 or p.score != score:
                score = p.score
                finish = i
            p.finish = finish
            if p.finish <= 8:
                p.position = chr(9311 + p.finish) # ①, ②, ③, …
            p.url = url_for('.person', person_id=p.person_id)

    def prepare_legal_formats(self) -> None:
        if getattr(self, 'legal_formats', None) is not None:
            self.legal_formats = list(map(add_season_num, list(sorted(self.legal_formats, key=legality.order_score)))) # type: ignore

    def prepare_matches(self) -> None:
        for m in getattr(self, 'matches', []):
            if m.get('date'):
                m.display_date = dtutil.display_date(m.date)
                m.date_sort = dtutil.dt2ts(m.date)
            if m.get('deck_id'):
                m.deck_url = url_for('deck', deck_id=m.deck_id)
            if m.get('opponent'):
                m.opponent_url = url_for('person', person_id=m.opponent)
            if m.get('opponent_deck_id'):
                m.opponent_deck_url = url_for('deck', deck_id=m.opponent_deck_id)

    def prepare_active_runs(self, o: Any) -> None:
        decks = getattr(o, 'decks', [])
        active, other = [], []
        for d in decks:
            if d.is_in_current_run():
                active.append(d)
            else:
                other.append(d)
        if len(active) > 0 and o.hide_active_runs:
            o.active_runs_text = ngettext('%(num)d active league run', '%(num)d active league runs', len(active)) if len(active) > 0 else ''
            o.decks = other

    def babel_languages(self) -> List[Locale]:
        return APP.babel.list_translations()

    def TT_HELP_TRANSLATE(self) -> str:
        return gettext('Help us translate the site into your language')

    def setup_tournaments(self) -> None:
        info = tournaments.next_tournament_info()
        self.next_tournament_name = info['next_tournament_name']
        self.next_tournament_time = info['next_tournament_time']
        self.tournaments = sorted(tournaments.all_series_info(), key=lambda t: t.time)
        leagues = competition.load_competitions("c.competition_series_id IN (SELECT id FROM competition_series WHERE name = 'League') AND c.end_date > UNIX_TIMESTAMP(NOW())")
        end_date, prev_month, shown_end = None, None, False
        for t in self.tournaments:
            month = t.time.strftime('%b')
            if month != prev_month:
                t.month = month
                prev_month = month
            t.date = t.time.day
            if len(leagues) > 0 and t.time >= leagues[-1].start_date and t.time < leagues[-1].end_date:
                t.league = leagues.pop(-1)
                t.league.display = True
                end_date = t.league.end_date
            elif not shown_end and end_date and t.time >= end_date:
                t.league = {'class': 'begin', 'display': False}
                shown_end = True
            elif end_date:
                t.league = {'class': 'ongoing', 'display': False}


def seasonized_url(season_id: Union[int, str]) -> str:
    args = request.view_args.copy()
    if season_id == rotation.current_season_num():
        args.pop('season_id', None)
        endpoint = cast(str, request.endpoint).replace('seasons.', '')
    else:
        args['season_id'] = season_id
        prefix = '' if cast(str, request.endpoint).startswith('seasons.') else 'seasons.'
        endpoint = '{prefix}{endpoint}'.format(prefix=prefix, endpoint=request.endpoint)
    try:
        return url_for(endpoint, **args)
    except BuildError:
        return url_for(request.endpoint)

def add_season_num(f: str) -> str:
    if not 'Penny Dreadful ' in f:
        return f
    code = f.replace('Penny Dreadful ', '')
    num = rotation.season_num(code)
    return f.replace(code, f'{code} (Season {num})')
