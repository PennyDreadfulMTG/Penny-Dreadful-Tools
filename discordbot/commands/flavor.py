from discord.ext import commands

from discordbot.command import MtgContext
from magic import oracle
from magic.models import Card


@commands.command(aliases=['flavour'])
async def flavor(ctx: MtgContext, *, c: Card) -> None:
    """Flavor text of a card"""
    await ctx.single_card_text(c, flavor_text)

def flavor_text(c: Card) -> str:
    for printing in oracle.get_printings(c):
        if c.preferred_printing is not None and c.preferred_printing != printing.set_code:
            continue
        if printing.flavor is not None:
            return '\n' + printing.flavor + '\n-**' + oracle.get_set(printing.set_id).name + '**'
    if c.preferred_printing is not None:
        return f'No flavor text for {c.preferred_printing}'
    return 'No flavor text available'
