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
        for cost in c.get('mana_cost') or ():
            if c.layout == 'split':
                continue  # They might only be using one half so ignore it.
            if c.type_line == 'Instant — Trap':
                continue  # People often sideboard off-colour traps.
            if c.layout == 'modal_dfc':
                continue  # They might only be using one half so ignore it.
            if c.name == 'Damn':
                continue  # They might only be using the overload.
            card_symbols = mana.parse(cost)
            card_colors = mana.colors(card_symbols)
            colors.update(card_colors['required'])
            card_colored_symbols = mana.colored_symbols(card_symbols)
            colored_symbols += card_colored_symbols['required']
    return mana.order(colors), colored_symbols

def init() -> None:
    for name, colors in COLOR_COMBINATIONS.items():
        COLOR_COMBINATIONS_LOWER[name.lower()] = [color.lower() for color in colors]


init()
