import datetime

from discord.ext import commands

from discordbot import bot
from discordbot.command import MtgContext
from magic import rotation
from shared import dtutil


@commands.command()
async def hype(ctx: MtgContext) -> None:
    """Display the  latest rotation hype message."""
    until_rotation = rotation.next_rotation() - dtutil.now()
    last_run_time = rotation.last_run_time()
    if until_rotation < datetime.timedelta(7) and last_run_time is not None:
        msg = await bot.rotation_hype_message()
    if msg:
        await ctx.send(msg)
    else:
        await ctx.send('{ctx.author.mention}: No rotation hype message.')
