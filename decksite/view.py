import sys
from typing import Any, TypedDict, cast

import inflect
from babel import Locale
from flask import request, session, url_for
from flask_babel import gettext, ngettext
from werkzeug.routing import BuildError

from decksite import APP, get_season_id, prepare
from decksite.data import competition
from decksite.data.clauses import DEFAULT_GRID_PAGE_SIZE, DEFAULT_LIVE_TABLE_PAGE_SIZE
from decksite.deck_type import DeckType
from magic import card_price, legality, seasons, tournaments
from magic.models import Deck
from shared import dtutil, logger
from shared.container import Container
from shared_web import template
from shared_web.base_view import BaseView


class SeasonInfoDescription(TypedDict, total=False):
    name: str
    code: str
    code_lower: str
    disabled: bool
    num: int | None
    url: str
    decks_url: str
    league_decks_url: str
    competitions_url: str
    archetypes_url: str
    people_url: str
    cards_url: str
    rotation_changes_url: str
    tournament_leaderboards_url: str
    legality_name: str | None
    legal_cards_url: str | None

class View(BaseView):
    def __init__(self) -> None:
        super().__init__()
        self.max_price_text = card_price.MAX_PRICE_TEXT
        self.decks: list[Deck] = []
        self.active_runs_text: str = ''
        self.hide_active_runs = not session.get('admin', False)
        self.show_seasons: bool = False
        self.legal_formats: list[str] | None = None
        self.legal_seasons: list[int] | None = None
        self.cardhoarder_logo_url = url_for('static', filename='images/cardhoarder.png')
        self.is_person_page: bool | None = None
        self.next_tournament_name = None
        self.next_tournament_time = None
        self.tournaments: list[Container] = []
        self.content_class = 'content-' + self.__class__.__name__.lower()
        self.page_size = request.cookies.get('page_size', DEFAULT_LIVE_TABLE_PAGE_SIZE)
        self.grid_page_size = request.cookies.get('grid_page_size', DEFAULT_GRID_PAGE_SIZE)
        self.tournament_only: bool = False
        self.show_tournament_toggle = False
        self.is_deck_page = False
        self.has_external_source = False
        self.is_home_page = False
        self.tournament_rounds_info: list[dict[str, int | str]] = []
        self.matches: list[Container] = []
        self.hide_cardhoarder = False

    def season_id(self) -> int:
        return get_season_id()

    def season_name(self) -> str:
        return seasons.season_name(get_season_id())

    def season_code_lower(self) -> str:
        return seasons.season_code(get_season_id()).lower()

    def has_buttons(self) -> bool:
        return self.show_tournament_toggle or self.show_seasons or self.is_deck_page or self.has_external_source

    def all_seasons(self) -> list[SeasonInfoDescription]:
        seasonlist: list[SeasonInfoDescription] = []
        num = 1
        current_code = seasons.current_season_code()
        for code in seasons.SEASONS:
            seasonlist.append({
                'name': seasons.season_name(num),
                'code': code,
                'code_lower': code.lower(),
                'disabled': False,
                'num': num,
                'url': seasonized_url(num),
                'decks_url': url_for('seasons.decks', season_id=num),
                'league_decks_url': url_for('seasons.decks', season_id=num, deck_type=DeckType.LEAGUE.value),
                'competitions_url': url_for('seasons.competitions', season_id=num),
                'archetypes_url': url_for('seasons.archetypes', season_id=num),
                'people_url': url_for('seasons.people', season_id=num),
                'cards_url': url_for('seasons.cards', season_id=num),
                'rotation_changes_url': url_for('seasons.rotation_changes', season_id=num),
                'tournament_leaderboards_url': url_for('seasons.tournament_leaderboards', season_id=num),
                'legality_name': f'Penny Dreadful {code}',
                'legal_cards_url': 'https://pdmtgo.com/legal_cards.txt' if code == current_code else f'https://pdmtgo.com/{code}_legal_cards.txt',
            })
            num += 1
            if code == current_code:
                break
        seasonlist.append({
            'name': 'All Time',
            'code': 'all',
            'code_lower': 'all',
            'disabled': False,
            'num': None,
            'url': seasonized_url('all'),
            'decks_url': url_for('seasons.decks', season_id='all'),
            'league_decks_url': url_for('seasons.decks', season_id='all', deck_type=DeckType.LEAGUE.value),
            'competitions_url': url_for('seasons.competitions', season_id='all'),
            'archetypes_url': url_for('seasons.archetypes', season_id='all'),
            'people_url': url_for('seasons.people', season_id='all'),
            'cards_url': url_for('seasons.cards', season_id='all'),
            'rotation_changes_url': url_for('seasons.rotation_changes', season_id='all'),
            'tournament_leaderboards_url': url_for('seasons.tournament_leaderboards', season_id='all'),
            'legality_name': None,
            'legal_cards_url': None,
        })
        seasonlist.reverse()
        return seasonlist

    def season_chooser(self) -> list[SeasonInfoDescription]:
        ss = self.all_seasons()
        for season in ss:
            if self.legal_seasons and season['num'] and season['num'] not in self.legal_seasons:
                season['disabled'] = True
        return ss

    def favicon_url(self) -> str:
        return url_for('favicon', rest='.ico')

    def favicon_152_url(self) -> str:
        return url_for('favicon', rest='-152.png')

    def title(self) -> str:
        if not self.page_title():
            return 'pennydreadfulmagic.com'
        if get_season_id() == seasons.current_season_num():
            season = ''
        elif get_season_id() == 0:
            season = ' - All Time'
        else:
            season = f' - Season {get_season_id()}'
        return f'{self.page_title()}{season} – pennydreadfulmagic.com'

    # Site-wide notice in a banner at the top of every page, for very important things only!
    def notice_html(self) -> str:
        now = dtutil.now(dtutil.GATHERLING_TZ)
        if now > tournaments.pd500_date():
            cs = competition.load_competitions("ct.name = 'Gatherling' AND c.name LIKE '%%Penny Dreadful 500%%'", season_id=seasons.current_season_num(), should_load_decks=True)
            if len(cs) != 1 or not cs[0].decks or cs[0].decks[0].finish != 1:
                logger.warning('Wanted to display the PD500 winner but could not because of unexpected data')
                return ''
            c, d = cs[0], cs[0].decks[0]
            prepare.prepare_deck(d)
            return template.render_name('pd500winner', d | c)
        if tournaments.is_pd500_week(now):
            date = dtutil.display_date_with_date_and_year(tournaments.pd500_date())
            return template.render_name('pd500notice', {'url': url_for('pd500'), 'date': date})
        if tournaments.is_kick_off_week(now):
            date = dtutil.display_date_with_date_and_year(tournaments.kick_off_date())
            return template.render_name('kickoffnotice', {'url': url_for('kickoff'), 'date': date})
        if tournaments.is_super_saturday_week(now):
            date = dtutil.display_date_with_date_and_year(tournaments.super_saturday_date())
            return template.render_name('supersaturdaynotice', {'url': url_for('super_saturday'), 'date': date})
        return ''

    def page_title(self) -> str | None:
        pass

    def num_tournaments(self) -> str:
        r = inflect.engine().number_to_words(str(len(tournaments.all_series_info())))
        return cast(str, r)

    def rotation_text(self) -> str:
        return seasons.message()

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

    def show_season_icon(self) -> bool:
        return get_season_id() == 0

    def has_matches(self) -> bool:
        return len(self.matches) > 0

    def has_rounds(self) -> bool:
        return self.has_matches() and self.matches[0].get('round')

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
        prepare.prepare_cards(getattr(self, 'cards', []), getattr(self, 'tournament_only', False))

    def prepare_competitions(self) -> None:
        for c in getattr(self, 'competitions', []):
            c.competition_url = f'/competitions/{c.id}/'
            c.display_date = dtutil.display_date(c.start_date)
            c.competition_ends = '' if c.end_date < dtutil.now() else dtutil.display_date(c.end_date)
            c.date_sort = dtutil.dt2ts(c.start_date)
            c.league = c.type == 'League'

    def prepare_people(self) -> None:
        prepare.prepare_people(getattr(self, 'people', []))

    def prepare_archetypes(self) -> None:
        prepare.prepare_archetypes(getattr(self, 'archetypes', []), getattr(self, 'archetype', {}).get('id', None), getattr(self, 'tournament_only', False), self.season_id())

    def prepare_leaderboards(self) -> None:
        for leaderboard in getattr(self, 'leaderboards', []):
            prepare.prepare_leaderboard(leaderboard)

    def prepare_legal_formats(self) -> None:
        if getattr(self, 'legal_formats', None) is not None:
            self.legal_formats = list(map(add_season_num, sorted(self.legal_formats, key=legality.order_score)))  # type: ignore

    def prepare_matches(self) -> None:
        prepare.prepare_matches(getattr(self, 'matches', []), self.has_rounds())

    def prepare_active_runs(self, o: Any) -> None:
        decks = getattr(o, 'decks', [])
        active, other = [], []
        for d in decks:
            if d.is_in_current_run():
                active.append(d)
            else:
                other.append(d)
        if active and o.hide_active_runs:
            o.active_runs_text = ngettext('%(num)d active league run', '%(num)d active league runs', len(active)) if active else ''
            o.decks = other

    def babel_languages(self) -> list[Locale]:
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
            if leagues and t.time >= leagues[-1].start_date and t.time < leagues[-1].end_date:
                t.league = leagues.pop(-1)
                t.league['class'] = 'ongoing'
                t.league.display = True
                end_date = t.league.end_date
            elif not shown_end and end_date and t.time >= end_date:
                t.league = {'class': 'begin', 'display': False}
                shown_end = True
            elif end_date:
                t.league = {'class': 'ongoing', 'display': False}

    def setup_tournament_rounds(self) -> None:
        last_elimination_rounds = 0
        for entry in tournaments.rounds_info():
            if entry['min_players'] == entry['max_players']:
                num_players = str(entry['min_players'])
            elif entry['max_players'] == sys.maxsize:
                num_players = str(entry['min_players']) + '+'
            else:
                num_players = str(entry['min_players']) + '-' + str(entry['max_players'])
            note = ''
            if entry[tournaments.StageType.ELIMINATION_ROUNDS] != last_elimination_rounds:
                if entry[tournaments.StageType.ELIMINATION_ROUNDS] == 0:
                    note = '(swiss only)'
                elif entry['max_players'] == 2:
                    note = '(single match)'
                else:
                    n = 2 ** entry[tournaments.StageType.ELIMINATION_ROUNDS]
                    note = f'(top {n})'
                last_elimination_rounds = entry[tournaments.StageType.ELIMINATION_ROUNDS]
            self.tournament_rounds_info.append({
                'num_players': num_players,
                'swiss_rounds': entry[tournaments.StageType.SWISS_ROUNDS],
                'elimination_rounds': entry[tournaments.StageType.ELIMINATION_ROUNDS],
                'note': note,
            })


def seasonized_url(season_id: int | str) -> str:
    if request.view_args is not None:
        args = request.view_args.copy()
    else:
        args = {}
    if season_id == seasons.current_season_num():
        args.pop('season_id', None)
        endpoint = cast(str, request.endpoint).replace('seasons.', '')
    else:
        args['season_id'] = season_id
        prefix = '' if cast(str, request.endpoint).startswith('seasons.') else 'seasons.'
        endpoint = f'{prefix}{request.endpoint}'
    try:
        return url_for(endpoint, **args)
    except BuildError:
        return url_for(cast(str, request.endpoint))

def add_season_num(f: str) -> str:
    if 'Penny Dreadful ' not in f:
        return f
    code = f.replace('Penny Dreadful ', '')
    num = seasons.season_num(code)
    return f.replace(code, f'{code} (Season {num})')
