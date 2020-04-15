import re
from typing import Optional

from discord import Client, Emoji

from magic import oracle
from magic.models import Card


def find_emoji(emoji: str, client: Client) -> Optional[Emoji]:
    try:
        for guild in client.guilds:
            emojis = guild.emojis
            res = next((x for x in emojis if x.name == emoji), None)
            if res is not None:
                return res
        return None
    except AttributeError:
        return None

def replace_emoji(text: str, client: Client) -> str:
    if text is None:
        return ''
    output = text
    symbols = re.findall(r'\{([A-Z0-9/]{1,3})\}', text)
    for symbol in symbols:
        name = symbol
        name = name.replace('/', '')
        if len(name) == 1:
            if re.fullmatch('[0-9]', name):
                name = '0' + name
            else:
                name = name + name
        emoji = find_emoji(name, client)
        if emoji is not None:
            output = output.replace('{' + symbol + '}', str(emoji))
    return output

def info_emoji(c: Card, verbose: bool = False, show_legality: bool = True) -> str:
    s = ''
    if show_legality:
        if c.name in oracle.legal_cards():
            s += ':white_check_mark:'
        else:
            s += ':no_entry_sign:'
            if verbose:
                s += ' (not legal in PD)'
    if c.bugs:
        s += ':beetle:'
    return s
