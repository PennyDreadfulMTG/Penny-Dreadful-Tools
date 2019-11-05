from discordbot.command import MtgContext
from discord.ext import commands

from magic import multiverse
from shared import redis


@commands.check(commands.is_owner())
@commands.command()
async def rotate(ctx: MtgContext) -> None:
    """Perform all necessary post-rotation tasks."""
    await ctx.send('Rotating. This may take a while…')
    multiverse.init() # New Cards?
    multiverse.set_legal_cards() # PD current list
    multiverse.update_pd_legality() # PD previous lists
    if redis.REDIS:
        redis.REDIS.flushdb() # type: ignore, Clear the redis cache
    await ctx.send('Rotation complete, you probably want to restart me.')
