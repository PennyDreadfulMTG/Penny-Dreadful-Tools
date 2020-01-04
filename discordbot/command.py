import collections
import datetime
import re
from copy import copy
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from discord import File
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
            (r, mode, preferred_printing) = i
            if r.has_match() and not r.is_ambiguous():
                cards.extend(cards_from_names_with_mode([r.get_best_match()], mode, preferred_printing))
            elif r.is_ambiguous():
                cards.extend(cards_from_names_with_mode(r.get_ambiguous_matches(), mode, preferred_printing))
        await post_cards(client, cards, message.channel, message.author)

async def handle_command(message: Message, client: commands.Bot) -> None:
    ctx = await client.get_context(message, cls=MtgContext)
    await client.invoke(ctx)

def parse_queries(content: str) -> List[str]:
    to_scan = re.sub('`{1,3}[^`]*?`{1,3}', '', content, re.DOTALL) # Ignore angle brackets inside backticks. It's annoying in #code.
    queries = re.findall(r'\[?\[([^\]]*)\]\]?', to_scan)
    return [card.canonicalize(query) for query in queries if len(query) > 2]

def cards_from_names_with_mode(cards: Sequence[Optional[str]], mode: str, preferred_printing: str = None) -> List[Card]:
    oracle_cards = oracle.cards_by_name()
    return [copy_with_mode(oracle_cards[c], mode, preferred_printing) for c in cards if c is not None]

def copy_with_mode(oracle_card: Card, mode: str, preferred_printing: str = None) -> Card:
    c = copy(oracle_card)
    c['mode'] = mode
    c['preferred_printing'] = preferred_printing
    return c

def parse_mode(query: str) -> Tuple[str, str, Optional[str]]:
    mode = ''
    preferred_printing = None
    if query.startswith('$'):
        mode = '$'
        query = query[1:]

    if '|' in query:
        query, preferred_printing = query.split('|')

    return (mode, query, preferred_printing)

def results_from_queries(queries: List[str]) -> List[Tuple[SearchResult, str, Optional[str]]]:
    all_results = []
    for query in queries:
        mode, query, preferred_printing = parse_mode(query)
        result = searcher().search(query)
        all_results.append((result, mode, preferred_printing))
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
    result, mode, preferred_printing = results_from_queries([args])[0]
    if result.has_match() and not result.is_ambiguous():
        return cards_from_names_with_mode([result.get_best_match()], mode, preferred_printing)[0]
    if result.is_ambiguous():
        message = await send(channel, '{author}: Ambiguous name for {c}. Suggestions: {s} (click number below)'.format(author=author.mention, c=command, s=disambiguation(result.get_ambiguous_matches()[0:5])))
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
        with channel.typing():
            image_file = await image_fetcher.download_image_async(cards)
    if image_file is None:
        text += '\n\n'
        if len(cards) == 1:
            text += emoji.replace_emoji(cards[0].oracle_text, client)
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
    mana = emoji.replace_emoji('|'.join(requested_card.mana_cost or []), client)
    mana = mana.replace('|', ' // ')
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
        not_pd = configuration.get_list('not_pd')
        if str(self.channel.id) in not_pd or (getattr(self.channel, 'guild', None) is not None and str(self.channel.guild.id) in not_pd):
            show_legality = False

        name = c.name
        info_emoji = emoji.info_emoji(c, show_legality=show_legality)
        text = emoji.replace_emoji(f(c), self.bot)
        message = f'**{name}** {info_emoji} {text}'
        await self.send(message)

    async def post_cards(self, cards: List[Card], replying_to: Optional[Member] = None, additional_text: str = '') -> None:
        # this feels awkward, but shrug
        await post_cards(self.bot, cards, self.channel, replying_to, additional_text)
