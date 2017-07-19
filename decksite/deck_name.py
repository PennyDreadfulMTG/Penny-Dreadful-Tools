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
    'Yore-Tiller': ['W', 'U', 'B', 'R'],
    'UBRG': ['U', 'B', 'R', 'G'],
    'BRGW': ['B', 'R', 'G', 'W'],
    'RGWU': ['R', 'G', 'W', 'U'],
    'GWUB': ['G', 'W', 'U', 'B'],
    'Five Color': ['W', 'U', 'B', 'R', 'G']
}

def normalize(d):
    name = d.name
    name = name.lower()
    name = remove_pd(name)
    name = remove_hashtags(name)
    name = remove_brackets(name)
    name = expand_common_abbreviations(name)
    removed_colors = False
    without_colors = remove_colors(name)
    if name != without_colors:
        removed_colors = True
    name = without_colors
    if name == '' and d.get('archetype'):
        name = d.archetype
    if removed_colors or name == '':
        name = prepend_colors(name, d.colors)
    name = ucase_trailing_roman_numerals(name)
    return titlecase.titlecase(name)

def file_name(d):
    safe_name = normalize(d).replace(' ', '-')
    safe_name = re.sub('--+', '-', safe_name, flags=re.IGNORECASE)
    safe_name = re.sub('[^0-9a-z-]', '', safe_name, flags=re.IGNORECASE)
    return safe_name.strip('-')

def remove_pd(name):
    name = re.sub(r'(^| )[\[\(]?pd[hmst]?[\]\)]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?penny ?dreadful (sunday|monday|thursday)[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?penny ?dreadful[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?penny[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    return name

def remove_hashtags(name):
    name = re.sub(r'#[^ ]*', '', name).strip()
    return name

def remove_brackets(name):
    return re.sub(r'\[[^\]]*\]', '', name).strip()

def remove_colors(name):
    patterns = ['[WUBRG][WUBRG]*', '[WUBRG](/[WUBRG])*', 'Mono'] + list(COLOR_COMBINATIONS.keys())
    for pattern in patterns:
        name = re.sub('(^| ){pattern}( |$)'.format(pattern=pattern), ' ', name, flags=re.IGNORECASE).strip()
    return name

def expand_common_abbreviations(name):
    return name.replace('rdw', 'red deck wins').replace('ww', 'white weenie').replace('muc', 'mono blue control').replace('mbc', 'mono black control')

def prepend_colors(s, colors):
    colors_part = name_from_colors(colors, s)
    if s == 'suicide':
        return '{s} {colors_part}'.format(colors_part=colors_part, s=s)
    return '{colors_part} {s}'.format(colors_part=colors_part, s=s).strip()

def name_from_colors(colors, s=''):
    ordered = mana.order(colors)
    for name, symbols in COLOR_COMBINATIONS.items():
        if mana.order(symbols) == ordered:
            if len(symbols) == 1:
                if s.startswith('deck wins') or s.startswith('weenie') or s.startswith('suicide'):
                    return name
                return 'mono {name}'.format(name=name)
            return name
    return 'colorless'

def ucase_trailing_roman_numerals(name):
    last_word = name.split()[-1]
    if re.search('^[ivx]+$', last_word):
        name = re.sub('{last_word}$'.format(last_word=last_word), last_word.upper(), name)
    return name
