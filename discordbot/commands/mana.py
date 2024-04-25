import os
import pathlib

from interactions.ext.prefixed_commands import prefixed_command
from interactions.models import slash_command

from discordbot.command import MtgContext


@slash_command('mana')
async def mana(ctx: MtgContext) -> None:
    """Get Dr. Karsten's advice on number of colored sources of mana required."""
    await ctx.send_image_with_retry(os.path.join(pathlib.Path(__file__).parent.absolute(), 'img/mana-frank.png'))

m_mana = prefixed_command('mana')(mana.callback)
