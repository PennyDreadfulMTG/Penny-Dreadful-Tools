import re

from discord.ext import commands

from discordbot.command import MtgContext
from magic import multiverse
from shared import redis


@commands.check(commands.is_owner())
@commands.command()
async def rotate(ctx: MtgContext) -> None:
    """Perform all necessary post-rotation tasks."""
    multiverse.init() # New Cards?
    multiverse.set_legal_cards() # PD current list
    multiverse.update_pd_legality() # PD previous lists
    if redis.REDIS:
        redis.REDIS.flushdb() # type: ignore, Clear the redis cache
