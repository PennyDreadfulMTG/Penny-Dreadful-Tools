import sys

from dis_snek.models.checks import is_owner
from dis_snek.models.command import check, message_command

from discordbot.command import MtgContext


@message_command('reboot')
@check(is_owner())
async def restartbot(ctx: MtgContext) -> None:
    """Restart the bot."""
    await ctx.send('Rebooting!')
    await ctx.bot.stop()
    sys.exit(0)
