import os
import pathlib

from interactions import Extension, Client
from interactions.models import slash_command

from discordbot.command import MtgContext


class Mana(Extension):
    @slash_command('mana')
    async def mana(self, ctx: MtgContext) -> None:
        """Get Dr. Karsten's advice on number of colored sources of mana required."""
        await ctx.send_image_with_retry(os.path.join(pathlib.Path(__file__).parent.absolute(), 'img/mana-frank.png'))

def setup(bot: Client) -> None:
    Mana(bot)
