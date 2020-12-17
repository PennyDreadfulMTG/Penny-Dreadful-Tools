from discord.ext import commands

from discordbot.command import MtgContext
from magic import multiverse, oracle, whoosh_write


@commands.command(hidden=True)
async def update(ctx: MtgContext) -> None:
    """Forces an update to legal cards and bugs."""
    await ctx.send('Begun reloading legal cards and bugs.')
    await multiverse.set_legal_cards_async()
    oracle.legal_cards(force=True)
    await multiverse.update_bugged_cards_async()
    multiverse.rebuild_cache()
    whoosh_write.reindex()
    oracle.init(force=True)
    await ctx.send('Reloaded legal cards and bugs.')
