from collections.abc import Sequence

from flask import g, session, url_for

from decksite.data.models.person import Person
from decksite.deck_type import DeckType
from magic import fetcher, seasons
from magic.models import Card, Deck
from shared import dtutil
from shared.container import Container
from shared.pd_exception import InvalidDataException

# Take 'raw' items from the database and decorate them for use and display.

def prepare_cards(cs: list[Card], tournament_only: bool = False, season_id: int | str | None = None) -> None:
    for c in cs:
        prepare_card(c, tournament_only, season_id)

def prepare_card(c: Card, tournament_only: bool = False, season_id: int | str | None = None) -> None:
    season_name = seasons.current_season_name()
    prepare_card_urls(c, tournament_only, season_id)
    c.card_img_class = 'two-faces' if c.layout in ['transform', 'meld', 'modal_dfc'] else ''
    c.pd_legal = c.legalities.get(season_name, False) and c.legalities[season_name] != 'Banned'
    c.legal_formats = {k for k, v in c.legalities.items() if v != 'Banned'}
    c.non_pd_legal_formats = {k for k, v in c.legalities.items() if 'Penny Dreadful' not in k and v != 'Banned'}
    c.has_legal_format = len(c.legal_formats) > 0
    set_legal_icons(c)
    if c.get('num_decks') is not None:
        c.show_record = c.get('wins') or c.get('losses') or c.get('draws')
    if c.get('rank') == 0:
        c.display_rank = 'NEW'
    elif not c.get('rank'):
        c.display_rank = '-'
    else:
        c.display_rank = str(c.rank)

def prepare_card_urls(c: Card, tournament_only: bool = False, season_id: int | str | None = None) -> None:
    c.url = url_for_card(c, tournament_only, season_id)
    c.img_url = url_for_image(c.name)

def url_for_image(name: str) -> str:
    if g.get('url_cache') is None:
        g.url_cache = {}
    if g.url_cache.get('card_image') is None:
        g.url_cache['card_image'] = url_for('image', c='--cardname--')
    return g.url_cache['card_image'].replace('--cardname--', name)

def url_for_card(c: Card, tournament_only: bool = False, season_id: int | str | None = None) -> str:
    if g.get('url_cache') is None:
        g.url_cache = {}
    if g.url_cache.get('card_page') is None:
        if season_id is None or season_id == seasons.current_season_num():
            g.url_cache['card_page'] = url_for('.card', name='--cardname--', deck_type=DeckType.TOURNAMENT.value if tournament_only else None)
        else:
            g.url_cache['card_page'] = url_for('seasons.card', name='--cardname--', deck_type=DeckType.TOURNAMENT.value if tournament_only else None, season_id=season_id)
    return g.url_cache['card_page'].replace('--cardname--', c.name)

def prepare_decks(ds: list[Deck]) -> None:
    for d in ds:
        prepare_deck(d)

def prepare_deck(d: Deck) -> None:
    season_name = seasons.current_season_name()
    set_stars_and_top8(d)
    if d.get('colors') is not None:
        d.colors_safe = colors_html(d.colors, d.colored_symbols)
    if d.get('mtgo_username'):
        d.person_url = url_for('seasons.person', mtgo_username=d.mtgo_username, season_id=d.season_id)
    else:
        d.person_url = url_for('seasons.person', person_id=d.person_id, season_id=d.season_id)
    d.date_sort = dtutil.dt2ts(d.active_date)
    d.display_date = dtutil.display_date(d.active_date)
    d.show_record = d.wins or d.losses or d.draws
    if d.competition_id:
        d.competition_url = f'/competitions/{d.competition_id}/'
    d.url = f'/decks/{d.id}/'
    d.export_url = f'/export/{d.id}/'
    if d.is_in_current_run():
        d.active_safe = '<span class="active" title="Active in the current league">⊕</span>'
        d.stars_safe = f'{d.active_safe} {d.stars_safe}'.strip()
        d.source_sort = '1'
    d.source_is_external = not d.source_name == 'League'
    d.comp_row_len = len(f'{d.competition_name} (Piloted by {d.person}')
    if d.get('archetype_id', None):
        d.archetype_url = url_for('seasons.archetype', archetype_id=d.archetype_id, season_id=d.season_id)
    # We might be getting '43%'/'' from cache or '43'/None from the db. Cope with all possibilities.
    # It might be better to use display_omw and omw as separate properties rather than overwriting the numeric value.
    if d.get('omw') is None or d.omw == '':
        d.omw = ''
    elif '%' not in str(d.omw):
        d.omw = str(int(d.omw)) + '%'
    d.has_legal_format = len(d.legal_formats) > 0
    d.pd_legal = season_name in d.legal_formats
    d.non_pd_legal_formats = {f for f in d.legal_formats if season_name not in f}
    set_season_icon(d)
    set_legal_icons(d)
    if session.get('admin') or session.get('demimod') or not d.is_in_current_run():
        d.decklist = str(d)
    else:
        d.decklist = ''
    total, num_cards = 0, 0
    for c in d.maindeck:
        if c.card.cmc is None:
            c.card.cmc = 0
        if 'Land' not in c.card.type_line:
            num_cards += c['n']
            total += c['n'] * c.card.cmc
    d.average_cmc = round(total / max(1, num_cards), 2)

def prepare_people(ps: Sequence[Person]) -> None:
    for p in ps:
        if p.get('mtgo_username'):
            p.url = f'/people/{p.mtgo_username.lower()}/'
        else:
            p.url = f'/people/id/{p.id}/'
        p.show_record = p.get('wins', None) or p.get('losses', None) or p.get('draws', None)

def prepare_leaderboard(leaderboard: Sequence[Container]) -> None:
    for entry in leaderboard:
        if entry.get('finish', 9) <= 8:
            entry.position = chr(9311 + entry.finish)  # ①, ②, ③, …
        entry.url = url_for('seasons.person', person_id=entry.person_id, season_id=entry.season_id)

def prepare_matches(ms: Sequence[Container], show_rounds: bool = False) -> None:
    for m in ms:
        if m.get('date'):
            m.display_date = dtutil.display_date(m.date)
            m.date_sort = dtutil.dt2ts(m.date)
        if m.get('person'):
            m.person_url = url_for('person', mtgo_username=m.person)
        if m.get('deck_id'):
            m.deck_url = url_for('deck', deck_id=m.deck_id)
        if m.get('opponent'):
            m.opponent_url = url_for('.person', mtgo_username=m.opponent)
        else:
            m.opponent = 'BYE'
            m.opponent_url = False
        if m.get('opponent_deck_id'):
            m.opponent_deck_url = url_for('deck', deck_id=m.opponent_deck_id)
        else:
            m.opponent_deck_url = False
        if m.get('mtgo_id'):
            m.log_url = fetcher.logsite_url('/match/{id}/'.format(id=m.get('mtgo_id')))
        if show_rounds:
            m.display_round = display_round(m)

def display_round(m: Container) -> str:
    if not m.get('elimination'):
        return m.round
    if int(m.elimination) == 8:
        return 'QF'
    if int(m.elimination) == 4:
        return 'SF'
    if int(m.elimination) == 2:
        return 'F'
    raise InvalidDataException(f'Do not recognize round in {m}')

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
    elif d.finish and d.finish <= 16 and ('Penny Dreadful 500' in d.competition_name or 'Kick Off' in d.competition_name):
        d.top8_safe = '<span title="Top 16">⑯</span>'
        d.stars_safe = '★'
    elif d.finish and d.finish <= 32 and 'Kick Off' in d.competition_name:
        d.top8_safe = '<span title="Top 32">Ⓣ</span>'
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
        d.stars_safe = f'<span class="stars" title="Success Rating">{d.stars_safe}</span>'

def colors_html(colors: list[str], colored_symbols: list[str]) -> str:
    total = len(colored_symbols)
    if total == 0:
        return '<span class="mana" style="width: 3rem"></span>'
    s = ''
    for color in colors:
        n = colored_symbols.count(color)
        one_pixel_in_rem = 0.05  # See pd.css base font size for the derivation of this value.
        width = (3.0 - one_pixel_in_rem * len(colors)) / total * n
        s += f'<span class="mana mana-{color}" style="width: {width}rem"></span>'
    return s

def set_season_icon(d: Deck) -> None:
    code = seasons.season_code(d.season_id)
    d.season_icon = season_icon_link(code)

def set_legal_icons(o: Card | Deck) -> None:
    o.legal_icons = ''
    pd_formats = [fmt.replace('Penny Dreadful ', '') for fmt in o.legal_formats if 'Penny Dreadful ' in fmt]
    pd_formats.sort(key=lambda code: -seasons.SEASONS.index(code))
    for code in pd_formats:
        o.legal_icons += season_icon_link(code)

def season_icon_link(code: str) -> str:
    color = 'rare' if code in seasons.current_season_name() else 'common'
    n = seasons.SEASONS.index(code.upper()) + 1
    return f'<a href="/seasons/{n}/"><i class="ss ss-{code.lower()} ss-{color} ss-grad">S{n}</i></a>'
