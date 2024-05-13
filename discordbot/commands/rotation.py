from interactions import Extension, Client
from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import seasons


class Rotation(Extension):
    @slash_command()
    async def rotation(self, ctx: MtgContext) -> None:
        """Date of the next Penny Dreadful rotation."""
        await ctx.send(seasons.message())

def setup(bot: Client) -> None:
    Rotation(bot)
