# from interactions.models.checks import is_owner
from interactions import Client, Extension, check, is_owner, slash_command

from discordbot import reboot_utils
from discordbot.command import MtgContext
from discordbot.shared import channel_id
from shared import redis_wrapper


class Reboot(Extension):
    @slash_command(description='Restart the bot.')
    @check(is_owner())
    async def reboot(self, ctx: MtgContext) -> None:
        """Restart the bot."""
        if redis_wrapper.get_bool(reboot_utils.REBOOT_KEY):
            await ctx.send('A reboot is already scheduled.')
            return

        await ctx.send('Scheduling reboot')
        redis_wrapper.clear(reboot_utils.REBOOT_CHANNEL_KEY)
        requesting_channel_id = channel_id(ctx)
        if requesting_channel_id is not None:
            redis_wrapper.store(reboot_utils.REBOOT_CHANNEL_KEY, requesting_channel_id, ex=600)
        redis_wrapper.store(reboot_utils.REBOOT_KEY, True, ex=600)

def setup(bot: Client) -> None:
    Reboot(bot)
