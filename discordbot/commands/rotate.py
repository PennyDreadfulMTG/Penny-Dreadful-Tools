from discord.ext import commands

from discordbot.command import MtgContext
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
    if redis.REDIS: # Clear the redis cache
        redis.REDIS.flushdb() # type: ignore[no-untyped-call]
    await ctx.send('Rotation complete. You probably want to restart me.')
