from discord.ext import commands

from discordbot.command import MtgContext


@commands.check(commands.is_owner)
@commands.command(aliases=['restart', 'reboot'])
async def restartbot(ctx: MtgContext) -> None:
    """Restart the bot."""
    await ctx.send('Rebooting!')
    await ctx.bot.logout()
