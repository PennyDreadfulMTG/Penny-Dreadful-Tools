import re
from collections import OrderedDict

import titlecase
from better_profanity import profanity

from magic import mana
from magic.colors import COLOR_COMBINATIONS
from magic.models import Deck
from shared.pd_exception import InvalidDataException

WHITELIST = [
    '#JustNayaThings',
    "Bob's R Us",
    'Happy B DAY Adriana',
    'basically rakdos version of burn',
    'I WILL Make Combo Work in Season 15',
    'B U R N',
    'R E A N I M A T O R',
    'Meme Deck for #General',  # The capitalized #General here is removed in normalize in somewhat awkward fashion.
    'UB or Not UB? That Is the Question',
    'Rakdos Aggro but With Green Instead of Black',
    'The World Is So Black and White Nowadays',
    'Fix the Gargadon Bug Me Angy',
    'Red and Black Jank',
    'Black and Green',
    'Blue Dreadnought + More Red Hate',
    'Netdecking: Day 1',
    'Catch 22',
    'Clerks II',
    'Blue Man Group',
    'No Green Jeskai Ascendancy',
    'Orzhov Tokens 1.1: Not Even Sure if I Need the Black',
    'Happy Season 33!',
    "Datro's Idea, Tom's Manabase (I Am the Thomas Edison Of PD)",
]

PROFANITY_WHITELIST = [
    'weenie',
    'kill',
    'god',
    'hell',
    'weed',
    'titi',
]

PROFANITY_BLACKLIST = [
    'supremacia ariana',
    'fisting',
    'retarded',
    'erection',
    'erections',
    'hoe',
    'hoes',
    'greasefag',
]

ABBREVIATIONS = {
    'rdw': 'Red Deck Wins',
    'ww': 'White Weenie',
    'muc': 'Mono Blue Control',
    'mbc': 'Mono Black Control',
    'yore-tiller': 'WUBR',
    'glint-eye': 'UBRG',
    'dune-brood': 'BRGW',
    'ink-treader': 'RGWU',
    'witch-maw': 'GWUB',
}

MAX_NAME_LEN = 100

def normalize(d: Deck) -> str:
    try:
        name = d.original_name
        if whitelisted(name):
            return name
        name = titlecase.titlecase(name)
        if whitelisted(name):
            return name.replace('#General', '#general')
        name = replace_space_alternatives(name)
        name = remove_pd(name, d.season_id)
        name = remove_brackets(name)
        name = remove_season(name, d.season_id)
        name = remove_extra_spaces(name)
        name = remove_hashtags(name)
        name = remove_leading_deck(name)
        name = remove_extraneous_hyphens(name)
        unabbreviated = expand_common_abbreviations(name)
        if unabbreviated != name or name in ABBREVIATIONS.values():
            name = unabbreviated
        elif whitelisted(name):
            pass
        elif name and d.get('archetype_name') and name == d.get('archetype_name', '').lower():
            pass
        else:
            name = remove_profanity(name)
            name = normalize_version(name)
            name = add_colors_if_no_deck_name(name, d.get('colors'))
            name = normalize_colors(name, d.get('colors'))
            name = add_archetype_if_just_colors(name, d.get('archetype_name'))
            name = remove_mono_if_not_first_word(name)
        name = titlecase.titlecase(name)
        name = lowercase_version_marker(name)
        name = ucase_roman_numerals(name)
        name = correct_case_of_color_names(name)
        name = enforce_max_len(name)
        return name
    except ValueError as c:
        raise InvalidDataException(f'Failed to normalize {repr(d)}') from c

def file_name(d: Deck) -> str:
    safe_name = normalize(d).replace(' ', '-')
    safe_name = re.sub('--+', '-', safe_name, flags=re.IGNORECASE)
    safe_name = re.sub('[^0-9a-z-]', '', safe_name, flags=re.IGNORECASE)
    return safe_name.strip('-')

def replace_space_alternatives(name: str) -> str:
    name = name.replace('_', ' ')
    # Preserve periods in semver versions but otherwise replace them
    new_name = []
    for i, char in enumerate(name):
        if char == '.':
            prev_char_is_digit = i > 0 and name[i - 1].isdigit()
            next_char_is_digit = i < len(name) - 1 and name[i + 1].isdigit()
            new_name.append(' ' if not (prev_char_is_digit and next_char_is_digit) else char)
        else:
            new_name.append(char)
    return ''.join(new_name)

def remove_extra_spaces(name: str) -> str:
    return re.sub(r'\s+', ' ', name)

def remove_pd(name: str, season_id: int) -> str:
    name = re.sub(r'(^| )[\[({]?pd(?:[hmstf]|500|' + str(season_id) + r')?[])}]?([ -]|$)', '\\1\\2', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[({]?pd ?-?[])}]?', '\\1', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[({]?penny ?dreadful (sunday|monday|thursday)[])}]?( |$)', '\\1\\3', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[({]?penny ?dreadful[])}]?( |$)', '\\1\\2', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(^| )[\[({]?penny[])}]?( |$)', '\\1\\2', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'penny-', '', name, flags=re.IGNORECASE).strip()
    return name

def remove_hashtags(name: str) -> str:
    name = re.sub(r'#[^ ]*', '', name).strip()
    return name

def remove_brackets(name: str) -> str:
    return re.sub(r'\[[^]]*]', '', name).strip()

def expand_common_abbreviations(name: str) -> str:
    for abbreviation, expansion in ABBREVIATIONS.items():
        name = re.sub(f'(^| ){abbreviation}( |$)', f'\\1{expansion}\\2', name, flags=re.IGNORECASE).strip()
    return name

def whitelisted(name: str) -> bool:
    for w in WHITELIST:
        if name.startswith(w):
            return True
    return False

def normalize_colors(name: str, colors: list[str]) -> str:
    patterns = ['[WUBRG]+', '[WUBRG](/[WUBRG])*']
    patterns += ['(White|Blue|Black|Red|Green)([/-](White|Blue|Black|Red|Green))+']
    patterns += list(COLOR_COMBINATIONS.keys())
    unique_color_words: OrderedDict = OrderedDict()
    for pattern in patterns:
        regex = regex_pattern(pattern)
        found = re.search(regex, name, flags=re.IGNORECASE)
        if found:
            color_word = found.group().strip()
            if is_true_match(color_word):
                unique_color_words[color_word] = True
    if len(unique_color_words) == 0:
        return name
    color_words = list(unique_color_words.keys())
    canonical_colors = canonicalize_colors(color_words)
    true_color = name_from_colors(canonical_colors)
    word = color_words[0]
    pattern = r'(^| )' + word + '( |$)'
    name = re.sub(pattern, ' ' + true_color + ' ', name).strip()
    for color_word in color_words[1:]:
        name = name.replace(color_word, '')
    if len(canonical_colors) == 1 and len(colors) == 1 and name.startswith(true_color) and not any(abbrev for abbrev in ABBREVIATIONS.values() if name.lower().startswith(abbrev.lower())) and word.lower() != 'colorless':
        name = f'Mono {name}'
    return re.sub(' +', ' ', name.strip())

# Don't let things like 'BRRR' and 'UWU' match [WUBRG]+ searches.
def is_true_match(color_word: str) -> bool:
    if not re.search('^[WUBRG]+$', color_word, flags=re.IGNORECASE):
        return True
    return len(set(color_word)) == len(color_word)

def canonicalize_colors(colors: list[str]) -> set[str]:
    color_words: set[str] = set()
    for color in colors:
        color_words.add(standardize_color_string(color))
    canonical_colors: set[str] = set()
    for color in color_words:
        for name, symbols in COLOR_COMBINATIONS.items():
            if name == color:
                canonical_colors = canonical_colors | set(symbols)
    return set(mana.order(canonical_colors))

def regex_pattern(pattern: str) -> str:
    return f'(?:^| )(?:mono[ -]?)?({pattern})(?: |$)'

def standardize_color_string(s: str) -> str:
    colors = re.sub('mono|/|-', '', s, flags=re.IGNORECASE).strip().lower()
    for k in COLOR_COMBINATIONS:
        find = k.lower()
        colors = colors.replace(find, ''.join(COLOR_COMBINATIONS[k]))
    return name_from_colors(set(colors.upper()))

def name_from_colors(colors: set[str]) -> str:
    ordered = mana.order(colors)
    for name, symbols in COLOR_COMBINATIONS.items():
        if mana.order(symbols) == ordered:
            return name
    return 'colorless'

def add_colors_if_no_deck_name(name: str, colors: set[str]) -> str:
    if name:
        return name
    return name_from_colors(colors)

def add_archetype_if_just_colors(name: str, archetype: str | None) -> str:
    if name.replace('Mono ', '') not in COLOR_COMBINATIONS.keys() or not archetype or archetype == 'Unclassified':
        return name
    archetype_contains_color_name = False
    for k in COLOR_COMBINATIONS:
        archetype_contains_color_name = archetype_contains_color_name or k in archetype
    new_name = ''
    if not archetype_contains_color_name:
        new_name += f'{name} '
    return new_name + archetype

def remove_mono_if_not_first_word(name: str) -> str:
    return re.sub('(.+) mono ', '\\1 ', name, flags=re.IGNORECASE)

def remove_profanity(name: str) -> str:
    profanity.load_censor_words(whitelist_words=PROFANITY_WHITELIST)
    profanity.add_censor_words(PROFANITY_BLACKLIST)
    name = profanity.censor(name, ' ').strip()
    name = re.sub(' +', ' ', name)  # We just replaced profanity with a space so compress spaces.
    return name

def remove_season(name: str, season_id: int) -> str:
    # Whitelist here because we remove_season even from whitelisted deck names
    if 'catch 22' in name.lower():
        return name
    name = _remove_season(r'(^|\W)[\[({]?(s|(season ?))' + str(season_id) + r'[])}]?\s*', name)
    # If you're mentioning 1, 2 or 3 it could be for any reason but if you're mentioning 4+, AND it matches the season_id of your deck, you're probably referencing the current season.
    if season_id >= 4:
        name = _remove_season(r'(?:[\[({]|\b)' + str(season_id) + r'(?:[])}]|\b)', name)
    return name

def _remove_season(pattern: str, name: str) -> str:
    season = re.search(pattern, name, flags=re.IGNORECASE)
    # Exempt decks using season number like a version number – 'Red Deck Wins 30.2'
    if season and not re.search(re.escape(season.group()) + r'\.\d', name):
        return name.replace(season.group(), ' ').strip()
    return name

def normalize_version(name: str) -> str:
    # Special exemption for 'bakert99 League Deck 1'-style names from Season 1. They don't need version-normalizing.
    if re.search(r'League Deck \d', name, flags=re.IGNORECASE):
        return name
    # If they have numbers in two places in the deck separated by letters
    # it's too likely to be something like '2 combos are better than 1'
    # so don't make any alterations
    if re.search(r'\d.*[a-uw-z,-].*\d', name, flags=re.IGNORECASE):
        return name
    name = normalize_parenthetical_versions(name)
    patterns = [
        r'(\W?)[\[({]?(?:v|ver|version|rev|mk) ?(\d[\.\d]*)(?:[])}]|\b)',  # Explicitly marked as a version
        r'(\s)[\[({]?(\d[\.\d]*)[])}]?$',  # Number at end of name
        r'(\s)[\[({]?(\d\.\d[\.\d]*)(?:[])}]|\b)',  # Dotted number somewhere in name
    ]
    for pattern in patterns:
        version = re.search(pattern, name, re.IGNORECASE)
        if not version:
            continue
        num = version.group(2)
        if not is_semver(num):
            continue
        # Exclude some known uses of numbers if it's not a dotted number ('This deck is tier 3', 'Count to 10', and similar)
        if '.' not in num and re.search(r'((tier|turn|to|till?|eason) ?)' + num, name, re.IGNORECASE):
            continue
        num = remove_semver_trailing_zeroes(num)
        spacer = ' ' if version.group(1) != '-' else version.group(1)
        name = replace_last(version.group(), spacer + 'v' + num, name).strip()
    # Trailing roman numerals are versions, too.
    roman_version = re.search(r'\s[\[({]?([ivx]+)[])}]?$', name, flags=re.IGNORECASE)
    if roman_version:
        num = parse_roman_sloppily(roman_version.group(1))
        name = replace_last(roman_version.group(), ' v' + str(num), name)
    return name


# We have quite a lot of deck names like My Cool Deck (1) (2). Turn that into My Cool Deck 1.2 here
def normalize_parenthetical_versions(name: str) -> str:
    ending_parenthesized_nums = re.search(r'\((\d+)\)(?: ?\((\d+)\))*$', name)
    if ending_parenthesized_nums:
        nums = [num for num in ending_parenthesized_nums.groups() if num]
        name = name.replace(ending_parenthesized_nums.group(), '.'.join(nums))
    return name

def is_semver(num: str) -> bool:
    try:
        parts = num.split('.')
        if int(parts[0]) >= 100:
            return False
        # Looks more like a date than a version ('12.30')?
        if len(parts) == 2 and len(parts[-1]) > 1 and parts[1][-1:] == '0':
            return False
        # Looks more like a price than a version ('0.02', '0.15')?
        if len(parts) == 2 and parts[0] == '0' and len(parts[1]) == 2:
            return False
        # Validate that all parts of the semver are ints
        [int(part) for part in parts]
    except ValueError:
        return False
    return True

def remove_semver_trailing_zeroes(s: str) -> str:
    return remove_semver_trailing_zeroes(s[:-2]) if s.endswith('.0') else s

# https://stackoverflow.com/questions/2556108/rreplace-how-to-replace-the-last-occurrence-of-an-expression-in-a-string
def replace_last(find: str, replace: str, subject: str) -> str:
    return replace.join(subject.rsplit(find, 1))

# Only allow I, V and X (anything higher than that is more likely to be a false positive). Allow invalid roman numerals like IIX for 8.
def parse_roman_sloppily(raw: str) -> int:
    mode, n = 'I', 0
    for c in reversed(raw.upper()):
        if c == 'I' and mode == 'I':
            n += 1
        elif c == 'I':
            n -= 1
        elif c == 'V' and mode in ['V', 'I']:
            n += 5
            mode = 'V'
        elif c == 'V':
            n -= 5
        elif c == 'X':
            n += 10
            mode = 'X'
    return n

def ucase_roman_numerals(name: str) -> str:
    numerals = re.search(r'\b([ivx]+)\b', name, flags=re.IGNORECASE)
    if numerals:
        name = name.replace(numerals.group(1), numerals.group(1).upper())
    return name

# See #6041.
def remove_leading_deck(name: str) -> str:
    return re.sub('^deck - ', '', name, flags=re.IGNORECASE)

def remove_extraneous_hyphens(name: str) -> str:
    s = re.sub('^ ?- ?', '', name)
    return re.sub(' ?- ?$', '', s)

def lowercase_version_marker(name: str) -> str:
    return re.sub(r'V(\d[\\.\d]*)', r'v\1', name)

def correct_case_of_color_names(name: str) -> str:
    for k in COLOR_COMBINATIONS:
        titlecase_k = titlecase.titlecase(k)
        name = name.replace(titlecase_k, k)
    return name

def enforce_max_len(name: str) -> str:
    return name if len(name) <= MAX_NAME_LEN else name[0:MAX_NAME_LEN] + '…'
