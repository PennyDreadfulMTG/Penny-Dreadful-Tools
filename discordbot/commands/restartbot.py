from dis_snek.models.checks import is_owner
from dis_snek.models.command import check, message_command

from discordbot.command import MtgContext
from shared import redis_wrapper


@message_command('reboot')
@check(is_owner())
async def restartbot(ctx: MtgContext) -> None:
    """Restart the bot."""
    await ctx.send('Scheduling reboot')
    redis_wrapper.store('discordbot:do_reboot', True)
