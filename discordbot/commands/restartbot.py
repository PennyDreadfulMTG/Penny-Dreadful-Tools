# from naff.models.checks import is_owner
from naff.models import prefixed_command  # ,check

from discordbot.command import MtgContext
from shared import redis_wrapper


@prefixed_command('reboot')
# @check(is_owner())
async def restartbot(ctx: MtgContext) -> None:
    """Restart the bot."""
    if redis_wrapper.get_bool('discordbot:do_reboot'):
        await ctx.send('rebooting!')
        await ctx.bot.stop()
        return

    await ctx.send('Scheduling reboot')
    redis_wrapper.store('discordbot:do_reboot', True)
