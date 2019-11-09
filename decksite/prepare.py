from typing import List, Union

from flask import session

from magic import rotation
from magic.models import Card, Deck
from shared import dtutil

# Take 'raw' items from the database and decorate them for use and display.

def prepare_decks(ds: List[Deck]) -> None:
    for d in ds:
        prepare_deck(d)

def prepare_deck(d: Deck) -> None:
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

def set_legal_icons(o: Union[Card, Deck]):
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
