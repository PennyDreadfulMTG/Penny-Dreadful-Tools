from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgContext


class Patreon(Extension):
    @slash_command('patreon')
    async def patreon(self, ctx: MtgContext) -> None:
        """Link to the PD Patreon."""
        await ctx.send('<https://www.patreon.com/silasary/>')


def setup(bot: Client) -> None:
    Patreon(bot)
