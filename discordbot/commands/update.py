from interactions import Client
from interactions.models import Extension, check, is_owner, slash_command

from discordbot.command import MtgContext
from magic import multiverse, oracle, whoosh_write
from shared import configuration


class Update(Extension):
    @slash_command()
    @check(is_owner())
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


def setup(bot: Client) -> None:
    Update(bot)
