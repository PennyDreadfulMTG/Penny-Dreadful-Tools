from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher


@commands.command()
async def pd500(ctx: MtgContext) -> None:
    """Display a link to the PD 500 information page."""
    await ctx.send(fetcher.decksite_url('/tournaments/pd500/'))
