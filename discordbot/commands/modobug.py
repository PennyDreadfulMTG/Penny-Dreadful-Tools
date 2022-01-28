from dis_snek.models import slash_command

from discordbot.command import MtgContext


@slash_command('modo-bug')
async def modobug(ctx: MtgContext) -> None:
    """Report a Magic Online bug."""
    await ctx.send('Report Magic Online issues at <https://github.com/PennyDreadfulMTG/modo-bugs/issues/new/choose>. Please follow the instructions there. Thanks!')
