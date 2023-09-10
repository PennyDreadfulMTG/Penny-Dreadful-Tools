from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher


@slash_command('kickoff')
async def kickoff(ctx: MtgContext) -> None:
    """Display a link to the Season Kick Off information page."""
    await ctx.send(fetcher.decksite_url('/tournaments/kickoff/'))
