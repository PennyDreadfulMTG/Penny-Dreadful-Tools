from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher


class PD500(Extension):
    @slash_command()
    async def pd500(self, ctx: MtgContext) -> None:
        """Display a link to the PD 500 information page."""
        await ctx.send(fetcher.decksite_url('/tournaments/pd500/'))


def setup(bot: Client) -> None:
    PD500(bot)
