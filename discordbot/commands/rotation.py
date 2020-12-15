from discord.ext import commands

from discordbot.command import MtgContext
from magic import seasons


@commands.command(aliases=['ro', 'rot', 'rotation'])
async def nextrotation(ctx: MtgContext) -> None:
    """Date of the next Penny Dreadful rotation."""
    await ctx.send(seasons.message())
