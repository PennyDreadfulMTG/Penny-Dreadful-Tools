import re
from typing import Dict, Optional

from interactions.client import Client
from interactions.models import PartialEmoji

from magic import rotation, seasons
from magic.models import Card
from shared import redis_wrapper as redis

CACHE: Dict[str, PartialEmoji] = {}

async def find_emoji(emoji: str, client: Client) -> Optional[PartialEmoji]:
    if res := CACHE.get(emoji):
        return res

    if not client.guilds:
        return None

    try:
        for guild in client.guilds:
            emojis = await guild.fetch_all_custom_emojis()
            res = next((x for x in emojis if x.name == emoji), None)
            if res is not None:
                CACHE[emoji] = res
                return res
        return None
    except AttributeError:
        return None

async def replace_emoji(text: str, client: Client) -> str:
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
        emoji = await find_emoji(name, client)
        if emoji is not None:
            output = output.replace('{' + symbol + '}', str(emoji))
    return output

def info_emoji(c: Card, verbose: bool = False, show_legality: bool = True, no_rotation_hype: bool = False, legality_format: str = 'Penny Dreadful') -> str:
    if legality_format == 'Penny Dreadful':
        legality_format = seasons.current_season_name()
    s = ''
    rot_emoji = ''
    if show_legality:
        legal = c.legal_in(legality_format)
        if legal:
            s += ':white_check_mark:'
        else:
            s += ':no_entry_sign:'
        if rotation.in_rotation() and not no_rotation_hype:
            rot_emoji = get_future_legality(c, legal)
            s += rot_emoji
        if not legal and verbose and not rot_emoji:
            s += f' (not legal in {legality_format})'

    if c.bugs:
        s += ':lady_beetle:'
    return s

def get_future_legality(c: Card, legal: bool) -> str:
    out_emoji = '<:rotating_out:702545628882010183>'
    for status, symbol in {'undecided': ':question:', 'legal': '<:rotating_in:702545611597021204>', 'notlegal': out_emoji}.items():
        if redis.sismember(f'decksite:rotation:summary:{status}', c.name):
            return symbol
    if rotation.read_rotation_files()[0] <= (rotation.TOTAL_RUNS / 2):
        return ':question:'
    return out_emoji
