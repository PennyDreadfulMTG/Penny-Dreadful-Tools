from io import IOBase
from pathlib import Path
from typing import Any, List, Optional, Protocol, Union

from dis_snek import Snake
from dis_snek.models import (TYPE_MESSAGEABLE_CHANNEL, AllowedMentions, BaseComponent, Context,
                             Embed, File, GuildText, InteractionContext, Member, Message,
                             MessageFlags, MessageReference, Snowflake_Type, Sticker, User)


def guild_id(ctx: Union[Context, TYPE_MESSAGEABLE_CHANNEL, None]) -> Optional[int]:
    if ctx is None:
        return None
    if isinstance(ctx, Context):
        ctx = ctx.channel
    if isinstance(ctx, GuildText):
        return ctx.id
    return None

def channel_id(ctx: Union[Context, TYPE_MESSAGEABLE_CHANNEL, None]) -> Optional[int]:
    if ctx is None:
        return None
    if isinstance(ctx, Context):
        if ctx.channel is None:
            if isinstance(ctx, InteractionContext):
                # Not sure why this happens
                return ctx.data.get('channel_id')
            return None
        return ctx.channel.id
    return ctx.id
