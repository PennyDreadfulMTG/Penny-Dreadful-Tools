from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher


@slash_command('pd500')
async def pd500(ctx: MtgContext) -> None:
    """Display a link to the PD 500 information page."""
    await ctx.send(fetcher.decksite_url('/tournaments/pd500/'))
