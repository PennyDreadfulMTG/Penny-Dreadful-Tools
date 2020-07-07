import re
from typing import Optional

from discord import Client, Emoji

from magic import oracle, rotation
from magic.models import Card
from shared import redis


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

def info_emoji(c: Card, verbose: bool = False, show_legality: bool = True, no_rotation_hype: bool = False) -> str:
    s = ''
    rot_emoji = ''
    if show_legality:
        legal = c.name in oracle.legal_cards()
        if legal:
            s += ':white_check_mark:'
        else:
            s += ':no_entry_sign:'
        if rotation.in_rotation() and not no_rotation_hype:
            rot_emoji = get_future_legality(c, legal)
            s += rot_emoji
        if not legal and verbose and not rot_emoji:
            s += ' (not legal in PD)'

    if c.bugs:
        s += ':beetle:'
    return s

def get_future_legality(c: Card, legal: bool) -> str:
    out_emoji = '<:rotating_out:702545628882010183>'
    for status, symbol in {'undecided':':question:', 'legal':'<:rotating_in:702545611597021204>', 'notlegal':out_emoji}.items():
        if redis.sismember(f'decksite:rotation:summary:{status}', c.name):
            return symbol
    if rotation.read_rotation_files()[0] <= (rotation.TOTAL_RUNS / 2):
        return ':question:'
    if legal:
        return out_emoji
    return ''
