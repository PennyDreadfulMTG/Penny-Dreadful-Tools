from dis_snek import Snake
from dis_snek.models import Scale, check, is_owner, message_command, slash_command

from discordbot.command import MtgContext, slash_permission_pd_mods
from magic import multiverse, oracle, whoosh_write
from shared import configuration


class Update(Scale):
    @slash_command('update', default_permission=False)
    @slash_permission_pd_mods()
    async def update(self, ctx: MtgContext) -> None:
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

    m_update = message_command('update')(check(is_owner())(update.callback))

def setup(bot: Snake) -> None:
    Update(bot)
