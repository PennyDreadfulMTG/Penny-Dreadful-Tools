from interactions.models import slash_command

from discordbot.command import MtgContext


@slash_command('patreon')
async def patreon(ctx: MtgContext) -> None:
    """Link to the PD Patreon."""
    await ctx.send('<https://www.patreon.com/silasary/>')
