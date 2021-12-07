from dis_snek.models.application_commands import slash_command
from dis_snek.models.command import message_command

from discordbot.command import MtgContext
from magic import seasons


@slash_command('rotation')
async def nextrotation(ctx: MtgContext) -> None:
    """Date of the next Penny Dreadful rotation."""
    await ctx.send(seasons.message())

m_rotation = message_command('rotation')(nextrotation.callback)
m_ro = message_command('ro')(nextrotation.callback)
