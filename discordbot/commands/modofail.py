from interactions import Extension, Client
from interactions.models import slash_command

from discordbot.command import MtgContext
from shared import redis_wrapper as redis


class ModoFail(Extension):
    @slash_command('modofail')
    async def modofail(self, ctx: MtgContext) -> None:
        """Ding!"""
        n = redis.increment(f'modofail:{ctx.guild}')
        redis.expire(f'modofail:{ctx.guild}', 3600)
        await ctx.send(f':bellhop: **MODO fail** {n}')

def setup(bot: Client) -> None:
    ModoFail(bot)
