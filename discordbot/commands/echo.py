from dis_snek.models.application_commands import slash_command
from dis_snek.models.command import message_command

from discordbot import emoji
from discordbot.command import MtgContext
from dis_snek.annotations.argument_annotations import CMD_BODY

@message_command('echo')
async def echo(ctx: MtgContext, *, args: CMD_BODY) -> None:
    """Repeat after me…"""
    s = emoji.replace_emoji(args, ctx.bot)
    if not s:
        s = "I'm afraid I can't do that, Dave"
    await ctx.send(s)
