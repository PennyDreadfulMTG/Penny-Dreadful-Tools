from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgInteractionContext
from shared import fetch_tools


class Downtimes(Extension):
    @slash_command(description='Show Magic Online scheduled downtime information.')
    async def downtimes(self, ctx: MtgInteractionContext) -> None:
        await ctx.defer()
        await ctx.send(await fetch_tools.fetch_async('https://pennydreadfulmtg.github.io/modo-bugs/downtimes.txt'))

def setup(bot: Client) -> None:
    Downtimes(bot)
