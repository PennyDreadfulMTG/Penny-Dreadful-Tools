"""
Debug stuff
"""

from dis_snek.client import Snake
from dis_snek.const import __py_version__, __version__
from dis_snek.errors import CommandCheckFailure, ScaleLoadException
from dis_snek.models import MessageContext, check, message_command
from dis_snek.models.checks import is_owner
from dis_snek.models.context import Context
from dis_snek.models.scale import Scale

class PDDebug(Scale):
    @message_command('regrow')
    @check(is_owner())
    async def regrow(self, ctx: MessageContext, module: str) -> None:
        try:
            self.bot.regrow_scale(f'{__package__}.{module}')
            await ctx.message.add_reaction('🔁')
        except ScaleLoadException as e:
            if 'Unable to shed scale: No scale exists with name' in str(e):
                try:
                    self.bot.grow_scale(f'{__package__}.{module}')
                    await ctx.message.add_reaction('▶')
                except ScaleLoadException as c:
                    await ctx.send(c)
            else:
                await ctx.send(e)

    @regrow.error
    async def regrow_error(self, error: Exception, ctx: Context) -> None:
        if isinstance(error, CommandCheckFailure):
            return await ctx.send('You do not have permission to execute this command')
        raise

    @message_command('enable_debugger')
    @check(is_owner())
    async def debugger(self, ctx: MessageContext) -> None:
        self.bot.grow_scale('dis_snek.debug_scale')
        await ctx.send('Enabled')


def setup(bot: Snake) -> None:
    PDDebug(bot)
