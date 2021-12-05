import os
import pathlib

from dis_snek.models.application_commands import slash_command
from dis_snek.models.command import message_command
from dis_snek.models.file import File

from discordbot.command import MtgContext


@slash_command('mana')
async def mana(ctx: MtgContext) -> None:
    """Get Dr. Karsten's advice on number of colored sources of mana required."""
    with open(os.path.join(pathlib.Path(__file__).parent.absolute(), 'img/mana-frank.png'), 'rb') as f:
        img = File(f)
        await ctx.channel.send(file=img)

m_mana = message_command(mana.callback)
