from io import IOBase
from pathlib import Path
from typing import Any, List, Optional, Protocol, Union

from dis_snek import Snake
from dis_snek.models import File
from dis_snek.models.context import Context
from dis_snek.models.discord_objects.channel import TYPE_MESSAGEABLE_CHANNEL, GuildText
from dis_snek.models.discord_objects.components import BaseComponent
from dis_snek.models.discord_objects.embed import Embed
from dis_snek.models.discord_objects.message import AllowedMentions, Message, MessageReference
from dis_snek.models.discord_objects.sticker import Sticker
from dis_snek.models.enums import MessageFlags
from dis_snek.models.snowflake import Snowflake_Type


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
        return ctx.channel.id
    return ctx.id

class SendableContext(Protocol):
    channel: TYPE_MESSAGEABLE_CHANNEL
    bot: Snake

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
