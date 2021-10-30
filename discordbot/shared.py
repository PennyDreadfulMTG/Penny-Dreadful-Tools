from typing import Optional, Union
import discord

def guild_id(channel: Union[discord.TextChannel, discord.DMChannel, discord.GroupChannel]) -> Optional[int]:
    if isinstance(channel, discord.TextChannel):
        return channel.id
    return None
