import re

from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher


@commands.command(aliases=['who'])
async def whois(ctx: MtgContext, *, args: str) -> None:
    """Who is a person?"""
    mention = re.match(r'<@!?(\d+)>', args)
    if mention:
        async with ctx.typing():
            person = await fetcher.person_data_async(mention.group(1))
        if person is None:
            await ctx.send(f"I don't know who {mention.group(0)} is :frowning:")
            return
        await ctx.send(f"{mention.group(0)} is **{person['name']}** on MTGO")
    else:
        async with ctx.typing():
            person = await fetcher.person_data_async(args)
        if person is None or person.get('discord_id') is None:
            await ctx.send(f"I don't know who **{args}** is :frowning:")
            return
        if person.get('name') is None:
            await ctx.send(f"I know this person but I don't know their name. That's weird. Here's what I know: {person}")
            return
        await ctx.send(f"**{person['name']}** is <@{person['discord_id']}>")
