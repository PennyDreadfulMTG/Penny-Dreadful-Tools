from discord.ext import commands

from discordbot.command import MtgContext
from magic import multiverse, oracle


@commands.command(hidden=True)
async def update(ctx: MtgContext) -> None:
    """Forces an update to legal cards and bugs."""
    await ctx.send('Begun reloading legal cards and bugs.')
    multiverse.set_legal_cards()
    oracle.legal_cards(force=True)
    multiverse.update_bugged_cards()
    multiverse.rebuild_cache()
    multiverse.reindex()
    oracle.init(force=True)
    await ctx.send('Reloaded legal cards and bugs.')
