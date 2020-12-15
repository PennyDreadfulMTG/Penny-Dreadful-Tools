from typing import Dict
from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher, seasons
from magic.models import Card
from shared import fetch_tools


@commands.command(aliases=['h', 'hi'])
async def history(ctx: MtgContext, *, c: Card) -> None:
    """Show the legality history of the specified card and a link to its all time page."""
    await ctx.single_card_text(c, card_history, show_legality=False)

def card_history(c: Card) -> str:
    data: Dict[int, bool] = {}
    for format_name, status in c.legalities.items():
        if 'Penny Dreadful ' in format_name and status == 'Legal':
            season_id = seasons.SEASONS.index(
                format_name.replace('Penny Dreadful ', '')) + 1
            data[season_id] = True
    data[seasons.current_season_num()] = c.legalities.get('Penny Dreadful', None) == 'Legal'
    s = '   '
    for i in range(1, seasons.current_season_num() + 1):
        s += f'{i} '
        s += ':white_check_mark:' if data.get(i, False) else ':no_entry_sign:'
        s += '   '
    s = s.strip()
    s += '\n<' + fetcher.decksite_url('/seasons/all/cards/{name}/'.format(
        name=fetch_tools.escape(c.name, skip_double_slash=True))) + '>'
    return s
