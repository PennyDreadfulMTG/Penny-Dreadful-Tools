import re
from typing import List, Optional, Set

import titlecase
from profanity import profanity

from magic import mana
from magic.models.deck import Deck
from shared.pd_exception import InvalidDataException

WHITELIST = [
    '#justnayathings'
]

ABBREVIATIONS = {
    'rdw': 'red deck wins',
    'ww': 'white weenie',
    'muc': 'mono blue control',
    'mbc': 'mono black control',
    'yore-tiller': 'wubr',
    'glint-eye': 'ubrg',
    'dune-brood': 'brgw',
    'ink-treader': 'rgwu',
    'witch-maw': 'gwub'
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
    'WUBR': ['W', 'U', 'B', 'R'],
    'UBRG': ['U', 'B', 'R', 'G'],
    'BRGW': ['B', 'R', 'G', 'W'],
    'RGWU': ['R', 'G', 'W', 'U'],
    'GWUB': ['G', 'W', 'U', 'B'],
    'Five Color': ['W', 'U', 'B', 'R', 'G']
}

def normalize(d: Deck) -> str:
    try:
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
        elif name and d.get('archetype_name') and name == d.get('archetype_name', '').lower():
            pass
        else:
            name = add_colors_if_no_deckname(name, d.get('colors'))
            name = normalize_colors(name)
            name = add_archetype_if_just_colors(name, d.get('archetype_name'))
            name = remove_mono_if_not_first_word(name)
            name = remove_profanity(name)
        name = ucase_trailing_roman_numerals(name)
        name = titlecase.titlecase(name)
        return correct_case_of_color_names(name)
    except ValueError:
        raise InvalidDataException('Failed to normalize {d}'.format(d=repr(d)))

def file_name(d: Deck) -> str:
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
    patterns = ['[WUBRG][WUBRG]*', '[WUBRG](/[WUBRG])*']
    patterns += ['(White|Blue|Black|Red|Green)(/(White|Blue|Black|Red|Green))+']
    patterns += list(COLOR_COMBINATIONS.keys())
    unique_color_words = set()
    for pattern in patterns:
        regex = regex_pattern(pattern)
        found = re.search(regex, name, flags=re.IGNORECASE)
        if found:
            unique_color_words.add(found.group().strip())
    if len(unique_color_words) == 0:
        return name
    color_words = list(unique_color_words)
    canonical_colors = canonicalize_colors(color_words)
    true_color = name_from_colors(canonical_colors)
    name = name.replace(color_words[0], true_color, 1)
    for color_word in color_words[1:]:
        name = name.replace(color_word, '')
    if len(canonical_colors) == 1 and name.startswith(true_color):
        name = 'mono {name}'.format(name=name)
    return name.strip()

def canonicalize_colors(colors: List[str]) -> List[str]:
    color_words = []
    for color in colors:
        color_words.append(standardize_color_string(color))
    canonical_colors: Set[str] = set()
    for color in color_words:
        for name, symbols in COLOR_COMBINATIONS.items():
            if name == color:
                canonical_colors = canonical_colors | set(symbols)
    return mana.order(canonical_colors)

def regex_pattern(pattern: str) -> str:
    return '(^| )(mono[ -]?)?{pattern}( |$)'.format(pattern=pattern)

def standardize_color_string(s: str) -> str:
    colors = re.sub('mono|/|-', '', s, re.IGNORECASE).strip().lower()
    for k in COLOR_COMBINATIONS:
        find = k.lower()
        colors = colors.replace(find, ''.join(COLOR_COMBINATIONS[k]))
    return name_from_colors(list(colors.upper()))

def name_from_colors(colors: List[str]) -> str:
    ordered = mana.order(colors)
    for name, symbols in COLOR_COMBINATIONS.items():
        if mana.order(symbols) == ordered:
            return name
    return 'colorless'

def add_colors_if_no_deckname(name: str, colors: List[str]) -> str:
    if not name:
        name = name_from_colors(colors).strip()
    return name

def add_archetype_if_just_colors(name: str, archetype: Optional[str]) -> str:
    if name in COLOR_COMBINATIONS.keys() and archetype and archetype != 'Unclassified':
        return '{name} {archetype}'.format(name=name, archetype=archetype)
    return name

def remove_mono_if_not_first_word(name: str) -> str:
    return re.sub('(.+) mono ', '\\1 ', name)

def remove_profanity(name: str) -> str:
    profanity.load_words(['bitch'])
    profanity.set_censor_characters(' ')
    name = profanity.censor(name).strip()
    name = re.sub(' +', ' ', name) # We just replaced profanity with a space so compress spaces.
    return name

def ucase_trailing_roman_numerals(name: str) -> str:
    if not name:
        raise ValueError('Asked to remove trailing roman numerals from an empty deck name')
    last_word = name.split()[-1]
    if re.search('^[ivx]+$', last_word):
        name = re.sub('{last_word}$'.format(last_word=last_word), last_word.upper(), name)
    return name

def strip_leading_punctuation(name: str) -> str:
    return re.sub('^[^a-z0-9]*', '', name, flags=re.IGNORECASE)

def correct_case_of_color_names(name: str) -> str:
    for k in COLOR_COMBINATIONS:
        titlecase_k = titlecase.titlecase(k)
        name = name.replace(titlecase_k, k)
    return name
