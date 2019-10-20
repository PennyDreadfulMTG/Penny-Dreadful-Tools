from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher, rotation
from magic.models import Card


@commands.command(aliases=['a'])
async def history(ctx: MtgContext, *, c: Card) -> None:
    """Show the legality history of the specified card and a link to its all time page."""
    await ctx.send_single_card_text(c, card_history, show_legality=False)

def card_history(c: Card) -> str:
    seasons = {}
    for format_name, status in c.legalities.items():
        if 'Penny Dreadful ' in format_name and status == 'Legal':
            season_id = rotation.SEASONS.index(
                format_name.replace('Penny Dreadful ', '')) + 1
            seasons[season_id] = True
    seasons[rotation.current_season_num()] = c.legalities.get(
        'Penny Dreadful', None) == 'Legal'
    s = '   '
    for i in range(1, rotation.current_season_num() + 1):
        s += f'{i} '
        s += ':white_check_mark:' if seasons.get(i,
                                                 False) else ':no_entry_sign:'
        s += '   '
    s = s.strip()
    s += '\n' + fetcher.decksite_url('/seasons/all/cards/{name}/'.format(
        name=fetcher.internal.escape(c.name, skip_double_slash=True)))
    return s
