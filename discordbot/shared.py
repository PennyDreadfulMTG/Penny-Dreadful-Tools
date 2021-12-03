from typing import Optional

from dis_snek.models.discord_objects.channel import TYPE_MESSAGEABLE_CHANNEL, GuildText


def guild_id(channel: TYPE_MESSAGEABLE_CHANNEL) -> Optional[int]:
    if isinstance(channel, GuildText):
        return channel.id
    return None
