from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher, rotation, seasons


class Rotation(Extension):
    @slash_command()
    async def rotation(self, ctx: MtgContext) -> None:
        """Date of the next Penny Dreadful rotation."""
        msg = seasons.message()
        if rotation.in_rotation():
            msg += f'\nSee what\'s changing: {fetcher.decksite_url("/rotation/")}'
        await ctx.send(msg)

def setup(bot: Client) -> None:
    Rotation(bot)
