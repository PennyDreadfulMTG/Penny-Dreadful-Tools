from naff.models import prefixed_command, slash_command

from discordbot.command import MtgContext
from magic import fetcher


@slash_command('downtimes')
async def downtimes(ctx: MtgContext) -> None:
    await ctx.send(fetcher.downtimes())

m_downtimes = prefixed_command('downtime')(downtimes.callback)
