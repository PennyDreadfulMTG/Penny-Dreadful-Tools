from dis_snek.models.application_commands import slash_command
from dis_snek.models.command import message_command

from discordbot.command import MtgContext
from magic import fetcher


@slash_command('downtimes')
async def downtimes(ctx: MtgContext) -> None:
    await ctx.send(fetcher.downtimes())

m_downtimes = message_command('downtime')(downtimes.callback)
