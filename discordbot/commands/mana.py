import os
import pathlib

from interactions.models import File, slash_command
from interactions.ext.prefixed_commands import prefixed_command

from discordbot.command import MtgContext


@slash_command('mana')
async def mana(ctx: MtgContext) -> None:
    """Get Dr. Karsten's advice on number of colored sources of mana required."""
    with open(os.path.join(pathlib.Path(__file__).parent.absolute(), 'img/mana-frank.png'), 'rb') as f:
        img = File(f)
        await ctx.send(file=img)

m_mana = prefixed_command(mana.callback)  # type: ignore
