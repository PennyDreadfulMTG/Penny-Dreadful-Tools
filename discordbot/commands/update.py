from discordbot.command import MtgContext, slash_permission_pd_mods
from magic import multiverse, oracle, whoosh_write
from shared import configuration
from dis_snek.models.application_commands import Permission, slash_command, slash_permission


@slash_command('update', default_permission=False)
@slash_permission_pd_mods()
async def update(ctx: MtgContext) -> None:
    """Forces an update to legal cards and bugs."""
    if configuration.prevent_cards_db_updates.get():
        await ctx.send('Warning: Card DB is frozen')
    await ctx.send('Begun reloading legal cards and bugs.')
    await multiverse.set_legal_cards_async()
    oracle.legal_cards(force=True)
    await multiverse.update_bugged_cards_async()
    multiverse.rebuild_cache()
    whoosh_write.reindex()
    oracle.init(force=True)
    await ctx.send('Reloaded legal cards and bugs.')
