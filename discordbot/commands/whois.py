import re
from typing import Any, Dict

from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher


@commands.command(aliases=['who'])
async def whois(ctx: MtgContext, *, args: str) -> None:
    """Who is a person?"""
    mention = re.match(r'<@!?(\d+)>', args)
    async with ctx.typing():
        if mention:
            person = await fetcher.person_data_async(mention.group(1))
            if not_found(person) or person.get('name') is None:
                msg = f"I don't know who {mention.group(0)} is :frowning:"
            else:
                msg = f"{mention.group(0)} is **{person['name']}** on MTGO"
        else:
            person = await fetcher.person_data_async(args)
            if not_found(person) or person.get('discord_id') is None:
                msg = f"I don't know who **{args}** is :frowning:"
            else:
                msg = f"**{person['name']}** is <@{person['discord_id']}>"
        await ctx.send(msg)

def not_found(person: Dict[str, Any]) -> bool:
    return person is None or (person.get('error') is not None and person.get('code') == 'NOTFOUND')
