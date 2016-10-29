import re

from magic import mana

COLOR_COMBINATIONS = {
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
    'Bant': ['W', 'U', 'B'],
    'Esper': ['W', 'U', 'G'],
    'Grixis': ['U', 'B', 'R'],
    'Jund': ['B', 'R', 'G'],
    'Naya': ['W', 'R', 'G'],
    'Mardu': ['W', 'B', 'R'],
    'Temur': ['U', 'R', 'G'],
    'Abzan': ['W', 'B', 'G'],
    'Jeskai': ['W', 'U', 'R'],
    'Sultai': ['U', 'B', 'G'],
    'Yore-Tiller': ['W', 'U', 'B', 'R'],
    'Glint-Eye': ['U', 'B', 'R', 'G'],
    'Dune-Brood': ['B', 'R', 'G', 'W'],
    'Ink-Treader': ['R', 'G', 'W', 'U'],
    'Witch-Maw': ['G', 'W', 'U', 'B'],
    'Five Color': ['W', 'U', 'B', 'R', 'G']
}

def normalize(d):
    name = d.name
    name = remove_pd(name)
    name = remove_colors(name)
    if name == '' and d.archetype:
        name = d.archetype
    elif name == '':
        name = name_from_colors(d.colors)
    name = prepend_colors(name, d.colors)
    return name.title()

def remove_pd(name):
    name = re.sub('(^| )pd( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub('(^| )penny ?dreadful( |$)', '', name, flags=re.IGNORECASE).strip()
    return name

def remove_colors(name):
    patterns = ['[WUBRG][WUBRG]*', '[WUBRG](/[WUBRG])*', 'Mono'] + list(COLOR_COMBINATIONS.keys())
    for pattern in patterns:
        name = re.sub('(^| ){pattern}( |$)'.format(pattern=pattern), '', name, flags=re.IGNORECASE).strip()
    return name

def prepend_colors(s, colors):
    color_s = ''.join('{{{color}}}'.format(color=color) for color in mana.order(colors))
    return '{color_s} {s}'.format(color_s=color_s, s=s)

def name_from_colors(colors):
    ordered = mana.order(colors)
    for name, symbols in COLOR_COMBINATIONS.items():
        print('Comparing {symbols} and {colors}'.format(symbols=mana.order(symbols), colors=ordered))
        if mana.order(symbols) == ordered:
            return name
