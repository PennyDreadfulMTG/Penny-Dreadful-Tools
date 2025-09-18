import logging
import traceback
from typing import Any

from interactions import Client, Extension, OptionType, check, is_owner, slash_option
from interactions.client.errors import CommandException
from interactions.models import slash_command

from discordbot.command import MtgContext
from shared import settings


class ConfigError(CommandException):
    def __init__(self, scope: int, message: str | None = None, *args: Any) -> None:
        super().__init__(message, *args)
        self.scope = scope

class Configure(Extension):
    @slash_command()
    @slash_option('scope', "'channel' or 'server'", OptionType.STRING, True)
    @slash_option('setting', 'key=value', OptionType.STRING, True)
    @check(is_owner())
    async def configure(self, ctx: MtgContext, scope: str, setting: str) -> None:
        await ctx.send('Temporarily disabled please contact hello@pennydreadfulmagic.com')
        # if isinstance(ctx.author, User):
        #     await ctx.send("Can't configure DMs right now, sorry")
        #     return
        # if not ctx.author.guild_permissions.MANAGE_CHANNELS:
        #     await ctx.send("You don't have permission to configure this server.")
        #     return
        # if scope == 'channel':
        #     configuring = ctx.channel.id
        # elif scope in ['server', 'guild']:
        #     configuring = ctx.channel.guild.id  # type: ignore
        # else:
        #     await ctx.send('You need to configure one of `server` or `channel`.')
        #     return
        # try:
        #     key, value = setting.split('=', 1)
        # except ValueError as e:
        #     raise ConfigError(configuring) from e
        #
        # if key not in settings.CONFIGURABLE_NAMES:
        #     raise ConfigError(configuring)
        #
        # with settings.with_config_file(configuring):
        #     settings.SETTINGS[key].set(value)  # type: ignore

    @configure.error
    async def configure_error(self, error: Exception, ctx: MtgContext) -> None:
        if isinstance(error, ConfigError):
            await ctx.send(self.help_message(error.scope))
        elif isinstance(error, CommandException):
            await ctx.send(self.help_message(None))
        else:
            logging.error(error)
            traceback.print_exception(type(error), error, error.__traceback__)
            await ctx.send('There was an error processing your command')

    def help_message(self, scope: Any) -> str:
        msg = '/configure {server|channel} {SETTING=VALUE}\n\n'
        with settings.with_config_file(scope):
            for name in settings.CONFIGURABLE_NAMES:
                val = settings.SETTINGS[name].get()
                default = settings.SETTINGS[name].default_value
                doc = settings.SETTINGS[name].__doc__
                msg += f'{name}={val} (default: {default})\n> {doc}\n'
        return msg

def setup(bot: Client) -> None:
    Configure(bot)
