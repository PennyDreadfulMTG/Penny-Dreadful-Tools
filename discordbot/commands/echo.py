from interactions.ext.prefixed_commands import prefixed_command

from discordbot import emoji
from discordbot.command import MtgContext


@prefixed_command('echo')
async def echo(ctx: MtgContext, *, args: str) -> None:
    """Repeat after me…"""
    s = await emoji.replace_emoji(args, ctx.bot)
    if not s:
        s = "I'm afraid I can't do that, Dave"
    await ctx.send(s)
