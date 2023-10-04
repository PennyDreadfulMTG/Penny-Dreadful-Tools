"""
Debug stuff
"""

from interactions import Extension
from interactions.client import Client
from interactions.client.errors import CommandCheckFailure, ExtensionLoadException
from interactions.ext.prefixed_commands import PrefixedContext, prefixed_command
from interactions.models import check, is_owner


class PDDebug(Extension):
    @prefixed_command('regrow')
    @check(is_owner())
    async def regrow(self, ctx: PrefixedContext, module: str) -> None:
        try:
            self.bot.reload_extension(f'{__package__}.{module}')
            await ctx.message.add_reaction('🔁')
        except ExtensionLoadException as e:
            if 'Attempted to reload extension thats not loaded.' in str(e):
                try:
                    self.bot.load_extension(f'{__package__}.{module}')
                    await ctx.message.add_reaction('▶')
                except ExtensionLoadException as c:
                    await ctx.send(str(c))
            else:
                await ctx.send(str(e))

    @regrow.error
    async def regrow_error(self, error: Exception, ctx: PrefixedContext) -> None:
        if isinstance(error, CommandCheckFailure):
            await ctx.send('You do not have permission to execute this command')
            return
        raise

    @prefixed_command('enable_debugger')
    @check(is_owner())
    async def enable_debugger(self, ctx: PrefixedContext) -> None:
        self.bot.load_extension('interactions.ext.debug_extension')
        await self.bot.synchronise_interactions()
        await ctx.send('Enabled')


def setup(bot: Client) -> None:
    PDDebug(bot)
