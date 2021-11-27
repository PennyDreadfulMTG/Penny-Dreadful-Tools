from typing import Optional, Union

from dis_snek.models.discord_objects.channel import DMChannel, GuildText




def guild_id(channel: Union[GuildText, DMChannel]) -> Optional[int]:
    if isinstance(channel, GuildText):
        return channel.id
    return None
