from discord.ext import commands

from discordbot.command import MtgContext
from magic.models import Card


@commands.command(aliases=['l'])
async def legal(ctx: MtgContext, *, c: Card) -> None:
    """Announce whether the specified card is legal or not."""
    await ctx.single_card_text(c, lambda c: '')
