# from interactions.models.checks import is_owner
from interactions import Client, Extension, check, is_owner, slash_command

from discordbot.command import MtgContext
from shared import redis_wrapper


class Reboot(Extension):
    @slash_command()
    @check(is_owner())
    async def reboot(self, ctx: MtgContext) -> None:
        """Restart the bot."""
        if redis_wrapper.get_bool('discordbot:do_reboot'):
            await ctx.send('rebooting!')
            await ctx.bot.stop()
            return

        await ctx.send('Scheduling reboot')
        redis_wrapper.store('discordbot:do_reboot', True)


def setup(bot: Client) -> None:
    Reboot(bot)
