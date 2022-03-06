from io import IOBase
from pathlib import Path
from typing import Any, List, Optional, Protocol, Union

from dis_snek import Snake
from dis_snek.models import (TYPE_MESSAGEABLE_CHANNEL, AllowedMentions, BaseComponent, Context,
                             Embed, File, GuildText, InteractionContext, Message, MessageFlags,
                             MessageReference, Snowflake_Type, Sticker, User, Member)


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

class SendableContext(Protocol):
    channel: TYPE_MESSAGEABLE_CHANNEL
    bot: Snake
    invoked_name: str

    author: Union[Member, User]
    guild_id: Snowflake_Type
    message: Message

    async def send(
        self,
        content: Optional[str] = None,
        embeds: Optional[Union[List[Union['Embed', dict]], Union['Embed', dict]]] = None,
        components: Optional[
            Union[List[List[Union['BaseComponent', dict]]], List[Union['BaseComponent', dict]], 'BaseComponent', dict]
        ] = None,
        stickers: Optional[Union[List[Union['Sticker', 'Snowflake_Type']], 'Sticker', 'Snowflake_Type']] = None,
        allowed_mentions: Optional[Union['AllowedMentions', dict]] = None,
        reply_to: Optional[Union['MessageReference', 'Message', dict, 'Snowflake_Type']] = None,
        file: Optional[Union['File', 'IOBase', 'Path', str]] = None,
        tts: bool = False,
        flags: Optional[Union[int, 'MessageFlags']] = None,
        **kwargs: Any,
    ) -> 'Message':
        ...
