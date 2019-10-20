from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher
from magic.models import Card


@commands.command(aliases=['p'])
async def price(ctx: MtgContext, *, c: Card) -> None:
    """`!price {name}` Price information for a card."""
    await ctx.send_single_card_text(c, fetcher.card_price_string)
