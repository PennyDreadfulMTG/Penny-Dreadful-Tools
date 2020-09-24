from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher


@commands.command()
async def kickoff(ctx: MtgContext) -> None:
    """Display a link to the Season Kick Off information page."""
    await ctx.send(fetcher.decksite_url('/tournaments/kickoff/'))
