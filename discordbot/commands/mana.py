import os
import pathlib

from dis_snek.models import File, message_command, slash_command

from discordbot.command import MtgContext


@slash_command('mana')
async def mana(ctx: MtgContext) -> None:
    """Get Dr. Karsten's advice on number of colored sources of mana required."""
    with open(os.path.join(pathlib.Path(__file__).parent.absolute(), 'img/mana-frank.png'), 'rb') as f:
        img = File(f)
        await ctx.channel.send(file=img)

m_mana = message_command(mana.callback)
