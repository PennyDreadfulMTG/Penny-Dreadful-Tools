from interactions.ext.prefixed_commands import prefixed_command
from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import seasons


@slash_command('rotation')
async def nextrotation(ctx: MtgContext) -> None:
    """Date of the next Penny Dreadful rotation."""
    await ctx.send(seasons.message())

m_rotation = prefixed_command('rotation')(nextrotation.callback)
m_ro = prefixed_command('ro')(nextrotation.callback)
