from interactions.ext.prefixed_commands import prefixed_command
from interactions.models import MessageFlags, slash_command

from discordbot.command import MtgContext
from magic import rotation


@slash_command('hype')
async def hype(ctx: MtgContext) -> None:
    """Display the latest rotation hype message."""
    if rotation.in_rotation() and rotation.last_run_time() is not None:
        msg = await rotation.rotation_hype_message(True)
        await ctx.send(msg)
    else:
        await ctx.send(f'{ctx.author.mention}: No rotation hype message.', flags=MessageFlags.EPHEMERAL)

m_hype = prefixed_command('hype')(hype.callback)
