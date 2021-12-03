from typing import Any, List, Optional, Protocol, Union
from io import IOBase
from pathlib import Path
from dis_snek.models.enums import MessageFlags

from dis_snek import Snake
from dis_snek.models.discord_objects.channel import TYPE_MESSAGEABLE_CHANNEL, GuildText
from dis_snek.models import File
from dis_snek.models.discord_objects.components import BaseComponent
from dis_snek.models.discord_objects.embed import Embed
from dis_snek.models.discord_objects.message import AllowedMentions, Message, MessageReference
from dis_snek.models.discord_objects.sticker import Sticker
from dis_snek.models.snowflake import Snowflake_Type

def guild_id(channel: TYPE_MESSAGEABLE_CHANNEL) -> Optional[int]:
    if isinstance(channel, GuildText):
        return channel.id
    return None


class SendableContext(Protocol):
    channel: TYPE_MESSAGEABLE_CHANNEL
    bot: Snake

    async def send(
        self,
        content: Optional[str] = None,
        embeds: Optional[Union[List[Union["Embed", dict]], Union["Embed", dict]]] = None,
        components: Optional[
            Union[List[List[Union["BaseComponent", dict]]], List[Union["BaseComponent", dict]], "BaseComponent", dict]
        ] = None,
        stickers: Optional[Union[List[Union["Sticker", "Snowflake_Type"]], "Sticker", "Snowflake_Type"]] = None,
        allowed_mentions: Optional[Union["AllowedMentions", dict]] = None,
        reply_to: Optional[Union["MessageReference", "Message", dict, "Snowflake_Type"]] = None,
        file: Optional[Union["File", "IOBase", "Path", str]] = None,
        tts: bool = False,
        flags: Optional[Union[int, "MessageFlags"]] = None,
        **kwargs: Any
    ) -> "Message":
        ...

