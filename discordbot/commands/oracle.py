from discord.ext import commands

from discordbot.command import MtgContext
from magic.models import Card

@commands.command(aliases=['o'])
async def oracle(ctx: MtgContext, *, c: Card) -> None:
    """`!oracle {name}` Oracle text of a card."""
    await ctx.single_card_text(c, oracle_text)

def oracle_text(c: Card) -> str:
    return c.oracle_text
