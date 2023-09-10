from interactions.models import slash_command
from interactions.ext.prefixed_commands import prefixed_command

from discordbot.command import MtgContext
from magic import fetcher


@slash_command('downtimes')
async def downtimes(ctx: MtgContext) -> None:
    await ctx.send(fetcher.downtimes())

m_downtimes = prefixed_command('downtime')(downtimes.callback)
