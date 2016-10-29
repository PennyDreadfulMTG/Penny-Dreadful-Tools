import re

import titlecase

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
    'UBRG': ['U', 'B', 'R', 'G'],
    'BRGW': ['B', 'R', 'G', 'W'],
    'RGWU': ['R', 'G', 'W', 'U'],
    'GWUB': ['G', 'W', 'U', 'B'],
    'Five Color': ['W', 'U', 'B', 'R', 'G']
}

def normalize(d):
    name = d.name
    name = remove_pd(name)
    name = remove_colors(name)
    if name == '' and d.get('archetype'):
        name = d.archetype
    name = prepend_colors(name, d.colors)
    return titlecase.titlecase(name)

def remove_pd(name):
    name = re.sub(r'(^| )[\[\(]?pd[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?penny ?dreadful[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?penny[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    return name

def remove_colors(name):
    patterns = ['[WUBRG][WUBRG]*', '[WUBRG](/[WUBRG])*', 'Mono'] + list(COLOR_COMBINATIONS.keys())
    for pattern in patterns:
        name = re.sub('(^| ){pattern}( |$)'.format(pattern=pattern), '', name, flags=re.IGNORECASE).strip()
    return name

def prepend_colors(s, colors):
    prefix = name_from_colors(colors)
    return '{prefix} {s}'.format(prefix=prefix, s=s)

def name_from_colors(colors):
    ordered = mana.order(colors)
    for name, symbols in COLOR_COMBINATIONS.items():
        if mana.order(symbols) == ordered:
            if len(symbols) == 1:
                return 'Mono {name}'.format(name=name)
            return name
