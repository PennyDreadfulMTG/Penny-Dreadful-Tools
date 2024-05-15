from interactions import Client, Extension, slash_command

from discordbot.command import MtgInteractionContext
from shared import configuration, redis_wrapper


class Sync(Extension):
    @slash_command('sync', scopes=[configuration.pd_server_id.value])
    async def sync(self, ctx: MtgInteractionContext) -> None:
        """Sync your achievements"""
        key = f'discordbot:achievements:players:{ctx.author.id}'
        redis_wrapper.clear(key)
        await ctx.bot.sync_achievements(ctx.author, ctx.guild)
        await ctx.send('Done', ephemeral=True)

def setup(bot: Client) -> None:
    Sync(bot)
