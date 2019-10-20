from discord.ext import commands

from discordbot.command import MtgContext

@commands.command(aliases=['ro', 'rot'])
async def rotation(ctx: MtgContext) -> None:
    """`!rotation` Date of the next Penny Dreadful rotation."""
    await ctx.send(rotation.message())
