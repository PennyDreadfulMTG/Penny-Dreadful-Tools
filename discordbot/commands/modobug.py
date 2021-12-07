from dis_snek.models.application_commands import slash_command

from discordbot.command import MtgContext


@slash_command('modo-bug')
async def modobug(ctx: MtgContext) -> None:
    """Report a Magic Online bug."""
    await ctx.send('Report Magic Online issues at <https://github.com/PennyDreadfulMTG/modo-bugs/issues/new>. Please follow the instructions there. Thanks!')
