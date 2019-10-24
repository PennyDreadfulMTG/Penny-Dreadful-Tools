from discord.ext import commands

from discordbot.command import MtgContext

from magic import rotation


@commands.command(aliases=['ro', 'rot', 'rotation'])
async def nextrotation(ctx: MtgContext) -> None:
    """`!rotation` Date of the next Penny Dreadful rotation."""
    await ctx.send(rotation.message())
