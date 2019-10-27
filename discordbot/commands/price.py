from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher
from magic.models import Card


@commands.command(aliases=['p', 'pr'])
async def price(ctx: MtgContext, *, c: Card) -> None:
    """Price information for a card."""
    await ctx.single_card_text(c, fetcher.card_price_string)
