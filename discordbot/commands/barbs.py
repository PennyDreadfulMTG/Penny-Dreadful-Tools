from discord.ext import commands

from discordbot.command import MtgContext


@commands.command()
async def barbs(ctx: MtgContext) -> None:
    """Volvary's advice for when to board in Aura Barbs."""
    msg = "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."
    await ctx.send(msg)
