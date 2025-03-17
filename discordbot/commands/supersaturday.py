from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher


class SuperSaturday(Extension):
    @slash_command()
    async def supersaturday(self, ctx: MtgContext) -> None:
        """Display a link to the Super Saturday information page."""
        await ctx.send(fetcher.decksite_url('/tournaments/super-saturday/'))

def setup(bot: Client) -> None:
    SuperSaturday(bot)
