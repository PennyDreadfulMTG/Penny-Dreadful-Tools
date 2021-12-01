from dis_snek.models.application_commands import slash_command

from discordbot.command import MtgContext
from magic import seasons


@commands.command(aliases=['ro', 'rot', 'rotation'])
async def nextrotation(ctx: MtgContext) -> None:
    """Date of the next Penny Dreadful rotation."""
    await ctx.send(seasons.message())
