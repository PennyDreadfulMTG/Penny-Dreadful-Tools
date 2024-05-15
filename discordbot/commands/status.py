from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher


class Status(Extension):
    @slash_command()
    async def status(self, ctx: MtgContext) -> None:
        """Status of Magic Online."""
        mtgo_status = await fetcher.mtgo_status()
        await ctx.send(f'MTGO is {mtgo_status}')

def setup(bot: Client) -> None:
    Status(bot)
