
from discord.ext import commands

from discordbot.command import MtgContext
from shared import configuration


@commands.command
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
        await ctx.send('`!configure {server|channel} {SETTING=VALUE}.')
        return

    configuration.write(f'{configuring}.{key}', value)
