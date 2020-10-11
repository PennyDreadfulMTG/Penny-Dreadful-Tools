from collections import Counter
from typing import Dict, List, Sequence, Union

from flask import g, session, url_for

from decksite.data.models.person import Person
from decksite.deck_type import DeckType
from magic import oracle, rotation
from magic.models import Card, Deck
from shared import dtutil
from shared.container import Container

# Take 'raw' items from the database and decorate them for use and display.

NUM_MOST_COMMON_CARDS_TO_LIST = 10

def prepare_cards(cs: List[Card], tournament_only: bool = False) -> None:
    for c in cs:
        prepare_card(c, tournament_only)

def prepare_card(c: Card, tournament_only: bool = False) -> None:
    prepare_card_urls(c, tournament_only)
    c.card_img_class = 'two-faces' if c.layout in ['transform', 'meld', 'modal_dfc'] else ''
    c.pd_legal = c.legalities.get('Penny Dreadful', False) and c.legalities['Penny Dreadful'] != 'Banned'
    c.legal_formats = {k for k, v in c.legalities.items() if v != 'Banned'}
    c.non_pd_legal_formats = {k for k, v in c.legalities.items() if 'Penny Dreadful' not in k and v != 'Banned'}
    c.has_legal_format = len(c.legal_formats) > 0
    set_legal_icons(c)
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
        prepare_card(cs[v[0]], tournament_only)
        c.most_common_cards.append(cs[v[0]])
    c.has_most_common_cards = len(c.most_common_cards) > 0

def prepare_card_urls(c: Card, tournament_only: bool = False) -> None:
    c.url = url_for_card(c, tournament_only)
    c.img_url = url_for_image(c.name)

def url_for_image(name: str) -> str:
    if g.get('url_cache') is None:
        g.url_cache = {}
    if g.url_cache.get('card_image') is None:
        g.url_cache['card_image'] = url_for('image', c='--cardname--')
    return g.url_cache['card_image'].replace('--cardname--', name)

def url_for_card(c: Card, tournament_only: bool = False) -> str:
    if g.get('url_cache') is None:
        g.url_cache = {}
    if g.url_cache.get('card_page') is None:
        g.url_cache['card_page'] = url_for('.card', name='--cardname--', deck_type=DeckType.TOURNAMENT.value if tournament_only else None)
    return g.url_cache['card_page'].replace('--cardname--', c.name)

def prepare_decks(ds: List[Deck]) -> None:
    for d in ds:
        prepare_deck(d)

def prepare_deck(d: Deck) -> None:
    set_stars_and_top8(d)
    if d.get('colors') is not None:
        d.colors_safe = colors_html(d.colors, d.colored_symbols)
    if d.get('mtgo_username'):
        d.person_url = f'/people/{d.mtgo_username}/'
    else:
        d.person_url = f'/people/id/{d.person_id}/'
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
    d.source_is_external = not d.source_name == 'League'
    d.comp_row_len = len('{comp_name} (Piloted by {person}'.format(comp_name=d.competition_name, person=d.person))
    if d.get('archetype_id', None):
        d.archetype_url = '/archetypes/{id}/'.format(id=d.archetype_id)
    # We might be getting '43%'/'' from cache or '43'/None from the db. Cope with all possibilities.
    # It might be better to use display_omw and omw as separate properties rather than overwriting the numeric value.
    if d.get('omw') is None or d.omw == '':
        d.omw = ''
    elif '%' not in str(d.omw):
        d.omw = str(int(d.omw)) + '%'
    d.has_legal_format = len(d.legal_formats) > 0
    d.pd_legal = 'Penny Dreadful' in d.legal_formats
    d.non_pd_legal_formats = {f for f in d.legal_formats if 'Penny Dreadful' not in f}
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
            p.url = f'/people/{p.mtgo_username}/'
        else:
            p.url = f'/people/id/{p.id}/'
        p.show_record = p.get('wins', None) or p.get('losses', None) or p.get('draws', None)

def prepare_leaderboard(leaderboard: List[Container]) -> None:
    for entry in leaderboard:
        if entry.get('finish', 9) <= 8:
            entry.position = chr(9311 + entry.finish) # ①, ②, ③, …
        entry.url = url_for('.person', person_id=entry.person_id)

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

def set_legal_icons(o: Union[Card, Deck]) -> None:
    o.legal_icons = ''
    sets = rotation.SEASONS
    if 'Penny Dreadful' in o.legal_formats:
        icon = rotation.current_season_code().lower()
        n = sets.index(icon.upper()) + 1
        o.legal_icons += '<a href="{url}"><i class="ss ss-{code} ss-rare ss-grad">S{n}</i></a>'.format(url='/seasons/{id}/'.format(id=n), code=icon, n=n)
    past_pd_formats = [fmt.replace('Penny Dreadful ', '') for fmt in o.legal_formats if 'Penny Dreadful ' in fmt]
    past_pd_formats.sort(key=lambda code: -sets.index(code))
    for code in past_pd_formats:
        n = sets.index(code.upper()) + 1
        o.legal_icons += '<a href="{url}"><i class="ss ss-{set} ss-common ss-grad">S{n}</i></a>'.format(url='/seasons/{id}/'.format(id=n), set=code.lower(), n=n)
