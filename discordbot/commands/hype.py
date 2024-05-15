from interactions import Client, Extension
from interactions.models import MessageFlags, slash_command

from discordbot.command import MtgContext
from magic import rotation


class Hype(Extension):
    @slash_command('hype')
    async def hype(self, ctx: MtgContext) -> None:
        """Display the latest rotation hype message."""
        if rotation.in_rotation() and rotation.last_run_time() is not None:
            msg = await rotation.rotation_hype_message(True)
            await ctx.send(msg)
        else:
            await ctx.send(f'{ctx.author.mention}: No rotation hype message.', flags=MessageFlags.EPHEMERAL)

def setup(bot: Client) -> None:
    Hype(bot)
