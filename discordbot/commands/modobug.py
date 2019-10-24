from discord.ext import commands

from discordbot.command import MtgContext


@commands.command()
async def modobug(ctx: MtgContext) -> None:
    """Report a Magic Online bug."""
    await ctx.send('Report Magic Online issues at <https://github.com/PennyDreadfulMTG/modo-bugs/issues/new>. Please follow the instructions there. Thanks!')
