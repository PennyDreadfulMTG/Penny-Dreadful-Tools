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
        if printing.flavor is not None:
            return '\n' + printing.flavor + '\n-**' + oracle.get_set(printing.set_id).name + '**'
    return 'No flavor text available'
