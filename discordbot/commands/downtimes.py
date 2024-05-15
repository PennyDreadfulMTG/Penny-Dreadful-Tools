from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgContext


class Downtimes(Extension):
    @slash_command()
    async def downtimes(self, ctx: MtgContext) -> None:
        await ctx.send('Temporarily disabled as malfunctioning')
        # await ctx.send(fetcher.downtimes())

def setup(bot: Client) -> None:
    Downtimes(bot)
