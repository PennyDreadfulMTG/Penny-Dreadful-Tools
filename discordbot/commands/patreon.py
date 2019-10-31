from discord.ext import commands

from discordbot.command import MtgContext


@commands.command()
async def patreon(ctx: MtgContext) -> None:
    """Link to the PD Patreon."""
    await ctx.send('<https://www.patreon.com/silasary/>')
