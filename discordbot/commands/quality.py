from typing import Annotated

from naff.models import CMD_BODY, prefixed_command

from discordbot.command import MtgContext


@prefixed_command('quality')
async def quality(ctx: MtgContext, product: Annotated[str, CMD_BODY] = None) -> None:
    """A reminder about everyone's favorite way to play digital Magic"""
    if not product:
        product = 'Magic Online'
    await ctx.send(f'**{product}** is a Quality™ Program.')
