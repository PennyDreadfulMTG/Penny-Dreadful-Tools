import collections
import datetime
import random
import re
import time
import traceback
from copy import copy
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import discord
from discord import FFmpegPCMAudio, File
from discord.channel import TextChannel
from discord.client import Client
from discord.ext import commands
from discord.member import Member
from discord.message import Message

from discordbot import emoji
from magic import card, fetcher, image_fetcher, oracle
from magic.models import Card
from magic.whoosh_search import SearchResult, WhooshSearcher
from shared import configuration, dtutil
from shared.lazy import lazy_property

DEFAULT_CARDS_SHOWN = 4
MAX_CARDS_SHOWN = 10
DISAMBIGUATION_EMOJIS = [':one:', ':two:', ':three:', ':four:', ':five:']
DISAMBIGUATION_EMOJIS_BY_NUMBER = {1 : '1⃣', 2 : '2⃣', 3 : '3⃣', 4 : '4⃣', 5 : '5⃣'}
DISAMBIGUATION_NUMBERS_BY_EMOJI = {'1⃣' : 1, '2⃣' : 2, '3⃣' : 3, '4⃣' : 4, '5⃣' : 5}

HELP_GROUPS: Set[str] = set()

@lazy_property
def searcher() -> WhooshSearcher:
    return WhooshSearcher()

async def respond_to_card_names(message: Message, client: Client) -> None:
    # Don't parse messages with Gatherer URLs because they use square brackets in the querystring.
    if 'gatherer.wizards.com' in message.content.lower():
        return
    queries = parse_queries(message.content)
    if len(queries) > 0:
        await message.channel.trigger_typing()
        results = results_from_queries(queries)
        cards = []
        for i in results:
            (r, mode) = i
            if r.has_match() and not r.is_ambiguous():
                cards.extend(cards_from_names_with_mode([r.get_best_match()], mode))
            elif r.is_ambiguous():
                cards.extend(cards_from_names_with_mode(r.get_ambiguous_matches(), mode))
        await post_cards(client, cards, message.channel, message.author)

async def handle_command(message: Message, client: commands.Bot) -> None:
    parts = message.content.split(' ', 1)
    method = find_method(parts[0])
    args = ''
    if len(parts) > 1:
        args = parts[1].strip()
    if method is not None:
        try:
            async with message.channel.typing():
                pass
            await method(Commands, client=client, channel=message.channel, args=args, author=message.author)
        except Exception as e: # pylint: disable=broad-except
            print('Caught exception processing command `{cmd}`'.format(cmd=message.content))
            tb = traceback.format_exc()
            print(tb)
            await send(message.channel, '{author}: I know the command `{cmd}` but encountered an error while executing it.'.format(cmd=parts[0], author=message.author.mention))
            await getattr(Commands, 'bug')(Commands, channel=message.channel, args='Command failed with {c}: {cmd}\n\n```\n{tb}\n```'.format(c=e.__class__.__name__, cmd=message.content, tb=tb), author=message.author)
    else:
        ctx = await client.get_context(message, cls=MtgContext)
        await client.invoke(ctx)

def find_method(name: str) -> Optional[Callable]:
    cmd = name.lstrip('!').lower()
    if len(cmd) == 0:
        return None
    method = [m for m in dir(Commands) if m in (cmd, '_' + cmd)]
    if len(method) == 0:
        method = [m for m in dir(Commands) if m.startswith(cmd) or m.startswith('_{cmd}'.format(cmd=cmd))]
    if len(method) > 0:
        return getattr(Commands, method[0])
    return None

def build_help(readme: bool = False, cmd: str = None) -> str:
    def print_group(group: str) -> str:
        msg = ''
        for methodname in dir(Commands):
            if methodname.startswith('__'):
                continue
            method = getattr(Commands, methodname)
            if getattr(method, 'group', None) != group:
                continue
            msg += '\n' + print_cmd(method, readme)
        return msg

    def print_cmd(method: Callable, verbose: bool) -> str:
        if method.__doc__:
            if not method.__doc__.startswith('`'):
                return '`!{0}` {1}'.format(method.__name__, method.__doc__)
            return '{0}'.format(method.__doc__)
        if verbose:
            return '`!{0}` No Help Available'.format(method.__name__)
        return '`!{0}`'.format(method.__name__)

    if cmd:
        method = find_method(cmd)
        if method:
            return print_cmd(method, True)
        if cmd in HELP_GROUPS:
            return print_group(cmd)
        return '`{cmd}` is not a valid command.'.format(cmd=cmd)

    msg = print_group('Commands')
    if readme:
        msg += '\n# Aliases'
        msg += print_group('Aliases')
        msg += '\n# Developer Commands'
        msg += print_group('Developer')
    return msg

def cmd_header(group: str) -> Callable:
    HELP_GROUPS.add(group)
    def decorator(func: Callable) -> Callable:
        setattr(func, 'group', group)
        return func
    return decorator



# pylint: disable=too-many-public-methods, too-many-lines
class Commands:
    @cmd_header('Configuration')
    async def configure(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        try:
            mode, args = args.split(' ', 1)
        except ValueError:
            await send(channel, '`!configure {server|channel} {SETTING=VALUE}.')
            return
        if mode == 'channel':
            if not author.permissions_in(channel).manage_channels:
                await send(channel, "You don't have permsssion to configure this channel.")
                return
            configuring = channel.id
        elif mode in ['server', 'guild']:
            if not author.guild_permissions.manage_channels:
                await send(channel, "You don't have permsssion to configure this server.")
                return
            configuring = channel.guild.id
        else:
            await send(channel, 'You need to configure one of `server` or `channel`.')
            return
        try:
            key, value = args.split('=', 1)
        except ValueError:
            await send(channel, '`!configure {server|channel} {SETTING=VALUE}.')
            return

        configuration.write(f'{configuring}.{key}', value)

    @cmd_header('Commands')
    async def help(self, channel: TextChannel, args: str, author: Member, ** _: Dict[str, Any]) -> None:
        """`!help` Bot commands help."""
        if args:
            msg = build_help(cmd=args)
        else:
            msg = """[cardname] to get card details.
"""
            msg += build_help()
            msg += """

Suggestions/bug reports: <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Discord-Bot/issues/>

Want to contribute? Send a Pull Request."""

        dm_channel = author.dm_channel
        if dm_channel is None:
            dm_channel = await author.create_dm()

        try:
            if len(msg) > 2000:
                await send(dm_channel, msg[0:1999] + '…')
            else:
                await send(dm_channel, msg)
        except discord.errors.Forbidden:
            await send(channel, f"{author.mention}: I can't send you the help text because you have blocked me.")

    @cmd_header('Commands')
    async def modofail(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """Ding!"""
        if args.lower() == 'reset':
            self.modofail.count = 0
        if hasattr(author, 'voice') and author.voice is not None and author.voice.channel is not None:
            voice_channel = author.voice.channel
            voice = channel.guild.voice_client
            if voice is None:
                voice = await voice_channel.connect()
            elif voice.channel != voice_channel:
                voice.move_to(voice_channel)
            voice.play(FFmpegPCMAudio('ding.ogg'))
        if time.time() > self.modofail.last_fail + 60 * 60:
            self.modofail.count = 0
        self.modofail.count += 1
        self.modofail.last_fail = time.time()
        await send(channel, ':bellhop: **MODO fail** {0}'.format(self.modofail.count))
    modofail.count = 0
    modofail.last_fail = time.time()

    @cmd_header('Configuration')
    async def notpenny(self, channel: TextChannel, args: str, **_: Dict[str, Any]) -> None:
        """Don't show PD Legality in this channel"""
        existing = configuration.get_list('not_pd')
        if args == 'server' and getattr(channel, 'guild', None) is not None:
            cid = channel.guild.id
        else:
            cid = channel.id
        if str(cid) not in existing:
            existing.append(str(cid))
            configuration.write('not_pd', set(existing))
        if args == 'server':
            await send(channel, 'Disable PD legality marks for the entire server')
        else:
            await send(channel, 'Disable PD legality marks for this channel. If you wanted to disable for the entire server, use `!notpenny server` instead.')

    isPack1Pick1Ready = True

    @cmd_header('Commands')
    async def p1p1(self, client: Client, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """`!p1p1` Summon a pack 1, pick 1 game."""

        if Commands.isPack1Pick1Ready:
            Commands.isPack1Pick1Ready = False #Do not allow more than one p1p1 at the same time.
            cards = [oracle.cards_by_name()[name] for name in random.sample(oracle.legal_cards(), 15)]
            image_fetcher.download_image(cards) #Preload the cards to reduce the delay encountered between introduction and the cards.
            await send(channel, "Let's play the pack 1, pick 1 game. The rules are simple. You are drafting and you open this as your first pack. What do you take?")
            await post_cards(client, cards[0:5], channel, None, '')
            await post_cards(client, cards[5:10], channel, None, '')
            await post_cards(client, cards[10:], channel, None, '')
            Commands.isPack1Pick1Ready = True
        else:
            print('Pack1Pick1 was denied as it was still processing another one.')  #This command will be heavy enough by itself, make sure the bot doesn't process it too much.

    @cmd_header('Aliases')
    async def pdm(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """Alias for `!resources`."""
        # Because of the weird way we call and use methods on Commands we need…
        # pylint: disable=too-many-function-args
        await self.resources(self, channel, args, author)

    @cmd_header('Commands')
    async def random(self, client: Client, channel: TextChannel, args: str, **_: Dict[str, Any]) -> None:
        """`!random` A random PD legal card.
`!random X` X random PD legal cards."""
        number = 1
        additional_text = ''
        if len(args) > 0:
            try:
                number = int(args)
                if number > 10:
                    additional_text = "{number}? Tsk. Here's ten.".format(number=number)
                    number = 10
            except ValueError:
                pass
        cards = [oracle.cards_by_name()[name] for name in random.sample(oracle.legal_cards(), number)]
        await post_cards(client, cards, channel, None, additional_text)

    @cmd_header('Commands')
    async def randomdeck(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """`!randomdeck` A random deck from the current season."""
        blob = fetcher.internal.fetch_json(fetcher.decksite_url('/api/randomlegaldeck'))
        if 'error' in blob or 'url' not in blob:
            await send(channel, blob.get('msg', ''))
        else:
            ctn = blob.get('competition_type_name', None)
            if ctn is not None:
                if ctn == 'Gatherling' and blob['finish'] == 1:
                    record = 'won'
                elif ctn == 'Gatherling' and blob['finish'] <= blob['competition_top_n']:
                    record = f"made Top {blob['competition_top_n']} of"
                else:
                    draws = f"-{blob['draws']}" if blob['draws'] > 0 else ''
                    record = f"went {blob['wins']}-{blob['losses']}{draws} in"
                preamble = f"{blob['person']} {record} {blob['competition_name']} with this:\n"
            else:
                preamble = f"{blob['person']} posted this on {blob['source_name']}:\n"
            await send(channel, preamble + blob['url'])

    @cmd_header('Commands')
    async def resources(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!resources {args}` Useful pages related to `args`. Examples: 'tournaments', 'card Naturalize', 'deckcheck', 'league'."""
        results = {}
        if len(args) > 0:
            results.update(resources_resources(args))
            results.update(site_resources(args))
        s = ''
        if len(results) == 0:
            s = 'PD resources: <{url}>'.format(url=fetcher.decksite_url('/resources/'))
        elif len(results) > 10:
            s = '{author}: Too many results, please be more specific.'.format(author=author.mention)
        else:
            for url, text in results.items():
                s += '{text}: <{url}>\n'.format(text=text, url=url)
        await send(channel, s)

    @cmd_header('Developer')
    async def restartbot(self, client: Client, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """Restart the bot."""
        await send(channel, 'Rebooting!')
        await client.logout()

    @cmd_header('Commands')
    async def spoiler(self, client: Client, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!spoiler {cardname}`: Request a card from an upcoming set."""
        if len(args) == 0:
            return await send(channel, '{author}: Please specify a card name.'.format(author=author.mention))
        sfcard = fetcher.internal.fetch_json('https://api.scryfall.com/cards/named?fuzzy={name}'.format(name=args))
        if sfcard['object'] == 'error':
            return await send(channel, '{author}: {details}'.format(author=author.mention, details=sfcard['details']))
        imagename = '{set}_{number}'.format(set=sfcard['set'], number=sfcard['collector_number'])
        imagepath = '{image_dir}/{imagename}.jpg'.format(image_dir=configuration.get('image_dir'), imagename=imagename)
        if sfcard.get('card_faces') and sfcard.get('layout', '') != 'split':
            c = sfcard['card_faces'][0]
        else:
            c = sfcard
        fetcher.internal.store(c['image_uris']['normal'], imagepath)
        text = emoji.replace_emoji('{name} {mana}'.format(name=sfcard['name'], mana=c['mana_cost']), client)
        await send(channel, file=File(imagepath), content=text)
        oracle.scryfall_import(sfcard['name'])

def parse_queries(content: str) -> List[str]:
    to_scan = re.sub('`{1,3}[^`]*?`{1,3}', '', content, re.DOTALL) # Ignore angle brackets inside backticks. It's annoying in #code.
    queries = re.findall(r'\[?\[([^\]]*)\]\]?', to_scan)
    return [card.canonicalize(query) for query in queries if len(query) > 2]

def cards_from_names_with_mode(cards: Sequence[Optional[str]], mode: str) -> List[Card]:
    oracle_cards = oracle.cards_by_name()
    return [copy_with_mode(oracle_cards[c], mode) for c in cards if c is not None]

def copy_with_mode(oracle_card: Card, mode: str) -> Card:
    c = copy(oracle_card)
    c['mode'] = mode
    return c

def parse_mode(query: str) -> List[str]:
    mode = ''
    if query.startswith('$'):
        mode = '$'
        query = query[1:]
    return [mode, query]

def results_from_queries(queries: List[str]) -> List[Tuple[SearchResult, str]]:
    all_results = []
    for query in queries:
        mode, query = parse_mode(query)
        result = searcher().search(query)
        all_results.append((result, mode))
    return all_results

def complex_search(query: str) -> List[Card]:
    if query == '':
        return []
    _, cardnames = fetcher.search_scryfall(query)
    cbn = oracle.cards_by_name()
    return [cbn[name] for name in cardnames if cbn.get(name) is not None]

def roughly_matches(s1: str, s2: str) -> bool:
    return simplify_string(s1).find(simplify_string(s2)) >= 0

def simplify_string(s: str) -> str:
    s = ''.join(s.split())
    return re.sub(r'[\W_]+', '', s).lower()

def disambiguation(cards: List[str]) -> str:
    if len(cards) > 5:
        return ','.join(cards)
    return ' '.join([' '.join(x) for x in zip(DISAMBIGUATION_EMOJIS, cards)])

async def disambiguation_reactions(message: Message, cards: List[str]) -> None:
    for i in range(1, len(cards)+1):
        await message.add_reaction(DISAMBIGUATION_EMOJIS_BY_NUMBER[i])

async def single_card_or_send_error(channel: TextChannel, args: str, author: Member, command: str) -> Optional[Card]:
    if not args:
        await send(channel, '{author}: Please specify a card name.'.format(author=author.mention))
        return None
    result, mode = results_from_queries([args])[0]
    if result.has_match() and not result.is_ambiguous():
        return cards_from_names_with_mode([result.get_best_match()], mode)[0]
    if result.is_ambiguous():
        message = await send(channel, '{author}: Ambiguous name for {c}. Suggestions: {s}'.format(author=author.mention, c=command, s=disambiguation(result.get_ambiguous_matches()[0:5])))
        await disambiguation_reactions(message, result.get_ambiguous_matches()[0:5])
    else:
        await send(channel, '{author}: No matches.'.format(author=author.mention))
    return None

# pylint: disable=too-many-arguments
async def single_card_text(client: Client, channel: TextChannel, args: str, author: Member, f: Callable, command: str, show_legality: bool = True) -> None:
    c = await single_card_or_send_error(channel, args, author, command)
    if c is not None:
        name = c.name
        info_emoji = emoji.info_emoji(c, show_legality=show_legality)
        text = emoji.replace_emoji(f(c), client)
        message = f'**{name}** {info_emoji} {text}'
        await send(channel, message)

def site_resources(args: str) -> Dict[str, str]:
    results = {}
    match = re.match('^s? ?([0-9]*|all) +', args)
    if match:
        season_prefix = 'seasons/' + match.group(1)
        args = args.replace(match.group(0), '', 1).strip()
    else:
        season_prefix = ''
    if ' ' in args:
        area, detail = args.split(' ', 1)
    else:
        area, detail = args, ''
    if area == 'archetype':
        area = 'archetypes'
    if area == 'card':
        area = 'cards'
    if area == 'person':
        area = 'people'
    sitemap = fetcher.sitemap()
    matches = [endpoint for endpoint in sitemap if endpoint.startswith('/{area}/'.format(area=area))]
    if len(matches) > 0:
        detail = '{detail}/'.format(detail=fetcher.internal.escape(detail, True)) if detail else ''
        url = fetcher.decksite_url('{season_prefix}/{area}/{detail}'.format(season_prefix=season_prefix, area=fetcher.internal.escape(area), detail=detail))
        results[url] = args
    return results

def resources_resources(args: str) -> Dict[str, str]:
    results = {}
    words = args.split()
    resources = fetcher.resources()
    for title, items in resources.items():
        for text, url in items.items():
            asked_for_this_section_only = len(words) == 1 and roughly_matches(title, words[0])
            asked_for_this_section_and_item = len(words) == 2 and roughly_matches(title, words[0]) and roughly_matches(text, words[1])
            asked_for_this_item_only = len(words) == 1 and roughly_matches(text, words[0])
            the_whole_thing_sounds_right = roughly_matches(text, ' '.join(words))
            the_url_matches = roughly_matches(url, ' '.join(words))
            if asked_for_this_section_only or asked_for_this_section_and_item or asked_for_this_item_only or the_whole_thing_sounds_right or the_url_matches:
                results[url] = text
    return results

async def post_cards(
        client: Client,
        cards: List[Card],
        channel: TextChannel,
        replying_to: Optional[Member] = None,
        additional_text: str = ''
) -> None:
    if len(cards) == 0:
        await post_no_cards(channel, replying_to)
        return
    not_pd = configuration.get_list('not_pd')
    disable_emoji = str(channel.id) in not_pd or (getattr(channel, 'guild', None) is not None and str(channel.guild.id) in not_pd)
    cards = uniqify_cards(cards)
    if len(cards) > MAX_CARDS_SHOWN:
        cards = cards[:DEFAULT_CARDS_SHOWN]
    if len(cards) == 1:
        text = single_card_text_internal(client, cards[0], disable_emoji)
    else:
        text = ', '.join('{name} {legal} {price}'.format(name=card.name, legal=((emoji.info_emoji(card)) if not disable_emoji else ''), price=((fetcher.card_price_string(card, True)) if card.get('mode', None) == '$' else '')) for card in cards)
    if len(cards) > MAX_CARDS_SHOWN:
        image_file = None
    else:
        image_file = image_fetcher.download_image(cards)
    if image_file is None:
        text += '\n\n'
        if len(cards) == 1:
            text += emoji.replace_emoji(cards[0].text, client)
        else:
            text += 'No image available.'
    text += additional_text
    if image_file is None:
        await send(channel, text)
    else:
        await send_image_with_retry(channel, image_file, text)

async def post_no_cards(channel: TextChannel, replying_to: Member) -> None:
    if replying_to is not None:
        text = '{author}: No matches.'.format(author=replying_to.mention)
    else:
        text = 'No matches.'
    message = await send(channel, text)
    await message.add_reaction('❎')


async def send(channel: TextChannel, content: str, file: File = None) -> Message:
    new_s = escape_underscores(content)
    return await channel.send(file=file, content=new_s)

async def send_image_with_retry(channel: TextChannel, image_file: str, text: str = '') -> None:
    message = await send(channel, file=File(image_file), content=text)
    if message and message.attachments and message.attachments[0].size == 0:
        print('Message size is zero so resending')
        await message.delete()
        await send(channel, file=File(image_file), content=text)

def single_card_text_internal(client: Client, requested_card: Card, disable_emoji: bool) -> str:
    mana = emoji.replace_emoji(''.join(requested_card.mana_cost or []), client)
    legal = ' — ' + emoji.info_emoji(requested_card, verbose=True)
    if disable_emoji:
        legal = ''
    if requested_card.get('mode', None) == '$':
        text = '{name} {legal} — {price}'.format(name=requested_card.name, price=fetcher.card_price_string(requested_card), legal=legal)
    else:
        text = '{name} {mana} — {type}{legal}'.format(name=requested_card.name, mana=mana, type=requested_card.type_line, legal=legal)
    if requested_card.bugs:
        for bug in requested_card.bugs:
            text += '\n:beetle:{rank} bug: {bug}'.format(bug=bug['description'], rank=bug['classification'])
            if bug['last_confirmed'] < (dtutil.now() - datetime.timedelta(days=60)):
                time_since_confirmed = (dtutil.now() - bug['last_confirmed']).total_seconds()
                text += ' (Last confirmed {time} ago.)'.format(time=dtutil.display_time(time_since_confirmed, 1))
    return text

# See #5532 and #5566.
def escape_underscores(s: str) -> str:
    new_s = ''
    in_url, in_emoji = False, False
    for char in s:
        if char == ':':
            in_emoji = True
        elif char not in 'abcdefghijklmnopqrstuvwxyz_':
            in_emoji = False
        if char == '<':
            in_url = True
        elif char == '>':
            in_url = False
        if char == '_' and not in_url and not in_emoji:
            new_s += '\\_'
        else:
            new_s += char
    return new_s

# Given a list of cards return one (aribtrarily) for each unique name in the list.
def uniqify_cards(cards: List[Card]) -> List[Card]:
    # Remove multiple printings of the same card from the result set.
    results: Dict[str, Card] = collections.OrderedDict()
    for c in cards:
        results[card.canonicalize(c.name)] = c
    return list(results.values())

def guild_or_channel_id(channel: TextChannel) -> int:
    return getattr(channel, 'guild', channel).id

class MtgContext(commands.Context):
    async def send_image_with_retry(self, image_file: str, text: str = '') -> None:
        message = await self.send(file=File(image_file), content=text)
        if message and message.attachments and message.attachments[0].size == 0:
            print('Message size is zero so resending')
            await message.delete()
            await self.send(file=File(image_file), content=text)

    async def single_card_text(self, c: Card, f: Callable, show_legality: bool = True) -> None:
        name = c.name
        info_emoji = emoji.info_emoji(c, show_legality=show_legality)
        text = emoji.replace_emoji(f(c), self.bot)
        message = f'**{name}** {info_emoji} {text}'
        await self.send(message)

    async def post_cards(self, cards: List[Card], replying_to: Optional[Member] = None, additional_text: str = '') -> None:
        # this feels awkward, but shrug
        await post_cards(self.bot, cards, self.channel, replying_to, additional_text)
