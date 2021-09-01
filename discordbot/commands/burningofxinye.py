from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher, tournaments
from shared import dtutil


@commands.command(aliases=['burn', 'burning'])
async def burningofxinye(ctx: MtgContext) -> None:
    """Information about Burning of Xinye's rules."""
    await ctx.send('https://katelyngigante.tumblr.com/post/163849688389/why-the-mtgo-bug-that-burning-of-xinye-allows')
