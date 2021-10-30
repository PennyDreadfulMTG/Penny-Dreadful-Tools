import traceback
from discord.ext import commands

from discordbot.command import MtgContext
from shared import configuration, settings


class ConfigError(commands.BadArgument):
    def __init__(self, scope: int, message=None, *args):
        super().__init__(message=message, *args)
        self.scope = scope


@commands.command()
async def configure(ctx: MtgContext, scope: str, setting: str) -> None:
    if scope == 'channel':
        if not ctx.author.permissions_in(ctx.channel).manage_channels:
            await ctx.send("You don't have permsssion to configure this channel.")
            return
        configuring = ctx.channel.id
    elif scope in ['server', 'guild']:
        if not ctx.author.guild_permissions.manage_channels:
            await ctx.send("You don't have permsssion to configure this server.")
            return
        configuring = ctx.channel.guild.id
    else:
        await ctx.send('You need to configure one of `server` or `channel`.')
        return
    try:
        key, value = setting.split('=', 1)
    except ValueError:
        raise ConfigError(configuring)

    if not key in settings.CONFIGURABLE_NAMES:
        raise ConfigError(configuring)

    with settings.with_config_file(configuring):
        settings.SETTINGS[key].value = value

@configure.error
async def configure_error(ctx: MtgContext, error: Exception) -> None:
    if isinstance(error, ConfigError):
        await ctx.send(help_message(error.scope))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(help_message(None))
    else:
        print(error)
        traceback.print_exception(type(error), error, error.__traceback__)
        await ctx.send('There was an error processing your command')

def help_message(scope):
    msg = '!configure {server|channel} {SETTING=VALUE}\n\n'
    with settings.with_config_file(scope):
        for name in settings.CONFIGURABLE_NAMES:
            val = settings.SETTINGS[name].get()
            default = settings.SETTINGS[name].default_value
            doc = settings.SETTINGS[name].__doc__
            msg += f'{name}={val} (default: {default})\n> {doc}\n'
    return msg
