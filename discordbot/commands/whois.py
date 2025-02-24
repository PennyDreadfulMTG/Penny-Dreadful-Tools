from typing import Any

from interactions import Client
from interactions.models import Extension, OptionType, User, slash_command, slash_option

from discordbot.command import MtgContext
from magic import fetcher


class Whois(Extension):
    @slash_command('whois', sub_cmd_name='mtgo', sub_cmd_description='Info about a MTGO player')
    @slash_option('username', 'The username of the MTGO player', OptionType.STRING, required=True)
    async def whois_mtgo(self, ctx: MtgContext, username: str) -> None:
        msg = await whois_mtgo(username)
        await ctx.send(msg)

    @whois_mtgo.subcommand(sub_cmd_name='discord', sub_cmd_description='Info about a Discord user')
    @slash_option('mention', 'The mention of the Discord user', OptionType.USER, required=True)
    async def whois_discord(self, ctx: MtgContext, mention: User) -> None:
        msg = await whois_discord(mention)
        await ctx.send(msg)


async def whois_mtgo(args: str) -> str:
    person = await fetcher.person_data_async(args)
    if not_found(person) or person.get('discord_id') is None:
        msg = f"I don't know who **{args}** is :frowning:"
    else:
        msg = f"**{person['name']}** is <@{person['discord_id']}>"
    return msg

async def whois_discord(user: User) -> str:
    person = await fetcher.person_data_async(user.id)
    if person and person.get('name'):
        return f"{user.mention} is **{person['name']}** on MTGO"
    person = await fetcher.gatherling_whois(discord_id=user.id)
    name = person.get('mtgo_username')
    if name:
        return f'{user.mention} is **{name}** on MTGO'
    name = person.get('name')
    if name:
        return f'{user.mention} is **{name}** on Gatherling'

    return f"I don't know who {user.mention} is :frowning:"

def not_found(person: dict[str, Any]) -> bool:
    return person is None or (person.get('error') is not None and person.get('code') == 'NOTFOUND')

def setup(bot: Client) -> None:
    Whois(bot)
