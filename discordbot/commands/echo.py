from dis_snek.models import CMD_BODY, message_command

from discordbot import emoji
from discordbot.command import MtgContext


@message_command('echo')
async def echo(ctx: MtgContext, args: CMD_BODY) -> None:
    """Repeat after me…"""
    s = await emoji.replace_emoji(args, ctx.bot)
    if not s:
        s = "I'm afraid I can't do that, Dave"
    await ctx.send(s)
