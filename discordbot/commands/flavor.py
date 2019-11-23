from discord.ext import commands

from discordbot.command import MtgContext
from magic.models import Card
from magic import oracle


@commands.command(aliases=["flavour"])
async def flavor(ctx: MtgContext, *, c: Card) -> None:
        """Flavor text of a card"""
        await ctx.single_card_text(c, flavor_text)

def flavor_text(c: Card) -> str:
    for print in oracle.get_printings(c):
        if print.flavor is not None:
            return '\n' + print.flavor + "\n-**" + oracle.get_set(print.set_id).name + '**'
    return "No flavor text available"