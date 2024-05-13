"""
Debug stuff
"""

from interactions import Extension, slash_command
from interactions.client import Client
from interactions.client.errors import CommandCheckFailure, ExtensionLoadException
from interactions.models import check, is_owner

from discordbot.command import MtgContext


class PDDebug(Extension):
    @slash_command()
    @check(is_owner())
    async def regrow(self, ctx: MtgContext, module: str) -> None:
        try:
            self.bot.reload_extension(f'{__package__}.{module}')
            if ctx.message:
                await ctx.message.add_reaction('🔁')
        except ExtensionLoadException as e:
            if 'Attempted to reload extension thats not loaded.' in str(e):
                try:
                    self.bot.load_extension(f'{__package__}.{module}')
                    if ctx.message:
                        await ctx.message.add_reaction('▶')
                except ExtensionLoadException as c:
                    await ctx.send(str(c))
            else:
                await ctx.send(str(e))

    @regrow.error
    async def regrow_error(self, error: Exception, ctx: MtgContext) -> None:
        if isinstance(error, CommandCheckFailure):
            await ctx.send('You do not have permission to execute this command')
            return
        raise

    @slash_command()
    @check(is_owner())
    async def enable_debugger(self, ctx: MtgContext) -> None:
        self.bot.load_extension('interactions.ext.debug_extension')
        await self.bot.synchronise_interactions()
        await ctx.send('Enabled')


def setup(bot: Client) -> None:
    PDDebug(bot)
