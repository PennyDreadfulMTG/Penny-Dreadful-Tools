from typing import Optional

from discord.ext import commands

from discordbot.command import MtgContext


@commands.command()
async def quality(ctx: MtgContext, *, product: Optional[str] = None) -> None:
    """`!quality` A reminder about everyone's favorite way to play digital Magic"""
    if product is None:
        product = 'Magic Online'
    await ctx.send(f'**{product}** is a Quality™ Program.')
