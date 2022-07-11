from typing import Annotated
from naff.models import CMD_BODY, prefixed_command

from discordbot import emoji
from discordbot.command import MtgContext


@prefixed_command('echo')
async def echo(ctx: MtgContext, args: Annotated[str, CMD_BODY]) -> None:
    """Repeat after me…"""
    s = await emoji.replace_emoji(args, ctx.bot)
    if not s:
        s = "I'm afraid I can't do that, Dave"
    await ctx.send(s)
