import re
from typing import Optional

from discord.client import Client

from magic import oracle
from magic.card import Card


def find_emoji(emoji: str, client: Client) -> Optional[str]:
    try:
        for server in client.servers:
            emojis = server.emojis
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

def legal_emoji(c: Card, verbose: bool = False) -> str:
    if c.name in oracle.legal_cards():
        s = ':white_check_mark:'
        if c.bugs:
            s += ":beetle:"
    else:
        s = ':no_entry_sign:'
        if verbose:
            s += ' (not legal in PD)'
    return s
