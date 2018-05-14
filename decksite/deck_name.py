import re
from typing import TYPE_CHECKING, List, Match, Optional

import titlecase

from magic import mana

# pylint: disable=cyclic-import,unused-import
if TYPE_CHECKING:
    from decksite.data.deck import Deck

WHITELIST = [
    'White Green'
]

ABBREVIATIONS = {
    'rdw': 'red deck wins',
    'ww': 'white weenie',
    'muc': 'mono blue control',
    'mbc': 'mono black control',
}

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

def normalize(d: 'Deck') -> str:
    name = d.original_name
    name = name.lower()
    name = replace_space_alternatives(name)
    name = remove_pd(name)
    name = remove_hashtags(name)
    name = remove_brackets(name)
    name = strip_leading_punctuation(name)
    unabbreviated = expand_common_abbreviations(name)
    if unabbreviated != name or name in ABBREVIATIONS.values():
        name = unabbreviated
    elif whitelisted(name):
        pass
    else:
        name = add_colors_if_no_deckname(name, d.get('colors'))
        name = normalize_colors(name)
        name = add_archetype_if_just_colors(name, d.get('archetype_name'))
        name = remove_mono_if_not_first_word(name)
    name = ucase_trailing_roman_numerals(name)
    return titlecase.titlecase(name)

def file_name(d: 'Deck') -> str:
    safe_name = normalize(d).replace(' ', '-')
    safe_name = re.sub('--+', '-', safe_name, flags=re.IGNORECASE)
    safe_name = re.sub('[^0-9a-z-]', '', safe_name, flags=re.IGNORECASE)
    return safe_name.strip('-')

def replace_space_alternatives(name: str) -> str:
    return name.replace('_', ' ').replace('.', ' ')

def remove_pd(name: str) -> str:
    name = re.sub(r'(^| )[\[\(]?pd[hmstf]?[\]\)]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?penny ?dreadful (sunday|monday|thursday)[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?penny ?dreadful[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?penny[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?season ?[0-9]+[\[\(]?( |$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[\(]?S[0-9]+[\[\(]?', '', name, flags=re.IGNORECASE).strip()
    return name

def remove_hashtags(name: str) -> str:
    name = re.sub(r'#[^ ]*', '', name).strip()
    return name

def remove_brackets(name: str) -> str:
    return re.sub(r'\[[^\]]*\]', '', name).strip()

def expand_common_abbreviations(name: str) -> str:
    for abbreviation, expansion in ABBREVIATIONS.items():
        name = re.sub('(^| ){abbrev}( |$)'.format(abbrev=abbreviation), '\\1{expansion}\\2'.format(expansion=expansion), name, flags=re.IGNORECASE).strip()
    return name

def whitelisted(name: str) -> bool:
    for w in WHITELIST:
        if name.startswith(w):
            return True
    return False

def normalize_colors(name: str) -> str:
    patterns = ['[WUBRG][WUBRG]*', '[WUBRG](/[WUBRG])*'] + list(COLOR_COMBINATIONS.keys())
    for pattern in patterns:
        name = re.sub('(^| )(mono[ -]?)?{pattern}( |$)'.format(pattern=pattern), standard_color_with_spaces, name, flags=re.IGNORECASE).strip()
    return name

def standard_color_with_spaces(m: Match) -> str:
    name_without_mono = re.sub('(mono[ -]?)', '', m.group(0))
    name = standardize_color_string(name_without_mono)
    return ' {name} '.format(name=name)

def standardize_color_string(s: str) -> str:
    colors = re.sub('Mono|/|-', '', s).strip().lower()
    for k in COLOR_COMBINATIONS:
        find = k.lower()
        colors = colors.replace(find, ''.join(COLOR_COMBINATIONS[k]))
    return name_from_colors(list(colors.upper()))

def name_from_colors(colors: List[str]) -> str:
    ordered = mana.order(colors)
    for name, symbols in COLOR_COMBINATIONS.items():
        if mana.order(symbols) == ordered:
            if len(symbols) == 1:
                return 'mono {name}'.format(name=name)
            return name
    return 'colorless'

def add_colors_if_no_deckname(name: str, colors: List[str]) -> str:
    if not name:
        name = name_from_colors(colors)
    return name

def add_archetype_if_just_colors(name: str, archetype: Optional[str]) -> str:
    if name in COLOR_COMBINATIONS.keys() and archetype:
        return '{name} {archetype}'.format(name=name, archetype=archetype)
    return name

def remove_mono_if_not_first_word(name: str) -> str:
    return re.sub('(.+) mono ', '\\1 ', name)

def ucase_trailing_roman_numerals(name: str) -> str:
    last_word = name.split()[-1]
    if re.search('^[ivx]+$', last_word):
        name = re.sub('{last_word}$'.format(last_word=last_word), last_word.upper(), name)
    return name

def strip_leading_punctuation(name: str) -> str:
    return re.sub('^[^a-z0-9]*', '', name, flags=re.IGNORECASE)
