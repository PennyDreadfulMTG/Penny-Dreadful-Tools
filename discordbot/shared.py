from typing import Optional, Union

from interactions.models import (TYPE_MESSAGEABLE_CHANNEL, BaseContext, GuildText,
                                 InteractionContext)


def guild_id(ctx: Union[BaseContext, TYPE_MESSAGEABLE_CHANNEL, None]) -> Optional[int]:
    if ctx is None:
        return None
    if isinstance(ctx, BaseContext):
        ctx = ctx.channel
    if isinstance(ctx, GuildText):
        return ctx.id
    return None

def channel_id(ctx: Union[BaseContext, TYPE_MESSAGEABLE_CHANNEL, None]) -> Optional[int]:
    if ctx is None:
        return None
    if isinstance(ctx, BaseContext):
        if ctx.channel is None:
            if isinstance(ctx, InteractionContext):
                # Not sure why this happens
                return ctx.data.get('channel_id')
            return None
        return ctx.channel.id
    return ctx.id
