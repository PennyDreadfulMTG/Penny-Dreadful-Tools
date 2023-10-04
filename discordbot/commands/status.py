from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher


@slash_command('status')
async def status(ctx: MtgContext) -> None:
    """Status of Magic Online."""
    mtgo_status = await fetcher.mtgo_status()
    await ctx.send('MTGO is {status}'.format(status=mtgo_status))
