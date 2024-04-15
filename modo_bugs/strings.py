import itertools
import re
from typing import Any
from collections.abc import Iterable
from re import Match

METACATS = ['Cardset', 'Collection', 'Deck Building', 'Duel Scene', 'Leagues', 'Play Lobby', 'Trade']
CATEGORIES = ['Advantageous', 'Disadvantageous', 'Game Breaking', 'Avoidable Game Breaking', 'Graphical', 'Non-Functional ability']
BADCATS = ['Game Breaking']

CODE_REGEX = r'^Code: (.*)$'
BBT_REGEX = r'^Bug Blog Text: (.*)$'

DISCORD_REGEX = r'^Reported on Discord by (\w+#[0-9]+)$'
IMAGES_REGEX = r'^<!-- Images --> (.*)$'
REGEX_CARDREF = r'\[?\[([^\]]*)\]\]?'
REGEX_SEARCHREF = r'\{\{\{([\w:/^$" ]+)\}\}\}'

REGEX_BBCAT = r'^([\w ]+) ?(\([\w, ]+\))?'

BAD_AFFECTS_REGEX = r'Affects: (\[Card Name\]\(, \[Second Card name\], etc\)\r?\n)\['

FEEDBACK_LINK_REGEX = r'((http|https)\:\/\/)?feedback.wizards.com/forums/([a-zA-Z0-9\.\&\/\?\:@\-_=#])*'
FORUM_LINK_REGEX = r'((http|https)\:\/\/)?forums.mtgo.com/index.php\?threads/([a-zA-Z0-9\.\&\/\?\:@\-_=#/])*'

def remove_smartquotes(text: str) -> str:
    return text.replace('’', "'").replace('“', '"').replace('”', '"')

def strip_squarebrackets(title: str) -> str:
    def get_name(match: Match[str]) -> str:
        return match.group(1).strip()
    title = re.sub(REGEX_CARDREF, get_name, title)
    return title

def grouper(n: int, iterable: Iterable, fillvalue: Any | None = None) -> Iterable:
    """grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)

def get_cards_from_string(item: str) -> list[str]:
    cards = re.findall(REGEX_CARDREF, item)
    return cards

def set_body_field(body: str, field: str, value: str) -> str:
    regex = r'^' + field + r': (.*)$'
    line = f'{field}: {value}'
    m = re.search(regex, body, re.MULTILINE)
    if m:
        return re.sub(regex, line, body, flags=re.MULTILINE)
    return f'{body}\n{line}'

def get_body_field(body: str, field: str) -> str | None:
    if body is None:
        return None
    regex = r'^' + field + r': (.*)$'
    m = re.search(regex, body, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None
