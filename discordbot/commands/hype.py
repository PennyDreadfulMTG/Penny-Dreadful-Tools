import datetime

from dis_snek.models.application_commands import slash_command
from dis_snek.models.enums import MessageFlags

from discordbot import bot  # This is a circular import
from discordbot.command import MtgContext
from magic import rotation, seasons
from shared import dtutil


@slash_command('hype')
async def hype(ctx: MtgContext) -> None:
    """Display the latest rotation hype message."""
    until_rotation = seasons.next_rotation() - dtutil.now()
    last_run_time = rotation.last_run_time()
    msg = None
    if until_rotation < datetime.timedelta(7) and last_run_time is not None:
        msg = await bot.rotation_hype_message(True)
    if msg:
        await ctx.send(msg, flags=MessageFlags.EPHEMERAL)
    else:
        await ctx.send(f'{ctx.author.mention}: No rotation hype message.', flags=MessageFlags.EPHEMERAL)
