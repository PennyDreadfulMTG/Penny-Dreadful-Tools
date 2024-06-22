from collections import Counter

from magic import mana
from magic.models import Card

COLOR_COMBINATIONS_LOWER = {}

COLOR_COMBINATIONS = {
    'Colorless': ['C'],
    'White': ['W'],
    'Blue': ['U'],
    'Black': ['B'],
    'Red': ['R'],
    'Green': ['G'],
    'Azorius': ['W', 'U'],
    'Orzhov': ['W', 'B'],
    'Boros': ['W', 'R'],
    'Selesnya': ['W', 'G'],
    'Dimir': ['U', 'B'],
    'Izzet': ['U', 'R'],
    'Simic': ['U', 'G'],
    'Rakdos': ['B', 'R'],
    'Golgari': ['B', 'G'],
    'Gruul': ['R', 'G'],
    'Esper': ['W', 'U', 'B'],
    'Bant': ['W', 'U', 'G'],
    'Grixis': ['U', 'B', 'R'],
    'Jund': ['B', 'R', 'G'],
    'Naya': ['W', 'R', 'G'],
    'Mardu': ['W', 'B', 'R'],
    'Temur': ['U', 'R', 'G'],
    'Abzan': ['W', 'B', 'G'],
    'Jeskai': ['W', 'U', 'R'],
    'Sultai': ['U', 'B', 'G'],
    'WUBR': ['W', 'U', 'B', 'R'],
    'UBRG': ['U', 'B', 'R', 'G'],
    'BRGW': ['B', 'R', 'G', 'W'],
    'RGWU': ['R', 'G', 'W', 'U'],
    'GWUB': ['G', 'W', 'U', 'B'],
    'Five Color': ['W', 'U', 'B', 'R', 'G'],
}


def find_colors(cs: list[Card]) -> tuple[list[str], list[str]]:
    colors: set[str] = set()
    colored_symbols: list[str] = []
    for c in cs:
        card_colors = []
        card_colored_symbols = []
        if "you may pay {0} rather than pay this spell's mana cost" in c.oracle_text:
            continue  # Mostly for Ravenous Trap which people sideboard off color to play for the alternative cost.
        if c.name == 'Damn':
            continue  # They might only be using the front, or only using the overload.
        if 'you may begin the game with it on the battlefield' in c.oracle_text:
            continue  # You can play off-color leylines
        for cost in c.get('mana_cost') or ():
            face_colors = mana.parse(cost)
            card_colors.append(mana.colors(face_colors)['required'])
            card_colored_symbols.append(mana.colored_symbols(face_colors)['required'])
        colors_in_every_cost = set.intersection(*card_colors)
        colored_symbols_in_every_cost = find_common_symbols(card_colored_symbols)
        colors.update(colors_in_every_cost)
        colored_symbols += colored_symbols_in_every_cost
    return mana.order(colors), colored_symbols


def find_common_symbols(lists: list[list[str]]) -> list[str]:
    if not lists:
        return []
    common_counter = Counter(lists[0])
    for sublist in lists[1:]:
        common_counter &= Counter(sublist)
    return list(common_counter.elements())


def init() -> None:
    for name, colors in COLOR_COMBINATIONS.items():
        COLOR_COMBINATIONS_LOWER[name.lower()] = [color.lower() for color in colors]


init()
