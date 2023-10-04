from typing import Optional

from interactions.ext.prefixed_commands import prefixed_command

from discordbot.command import MtgContext


@prefixed_command('quality')
async def quality(ctx: MtgContext, *, product: Optional[str] = None) -> None:
    """A reminder about everyone's favorite way to play digital Magic"""
    if not product:
        product = 'Magic Online'
    await ctx.send(f'**{product}** is a Quality™ Program.')
