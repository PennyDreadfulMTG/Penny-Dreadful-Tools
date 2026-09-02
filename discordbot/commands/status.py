from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgInteractionContext
from magic import fetcher


class Status(Extension):
    @slash_command(description='Status of Magic Online.')
    async def status(self, ctx: MtgInteractionContext) -> None:
        """Status of Magic Online."""
        await ctx.defer()
        mtgo_status = await fetcher.mtgo_status()
        await ctx.send(f'MTGO is {mtgo_status}')

def setup(bot: Client) -> None:
    Status(bot)
