import collections
import datetime
import logging
import re
from collections.abc import Callable, Sequence
from copy import copy
from typing import TYPE_CHECKING, cast

import attr
import whoosh
from interactions import Client, SlashContext, global_autocomplete
from interactions.client.errors import Forbidden
from interactions.ext.prefixed_commands import PrefixedContext
from interactions.models import DM, TYPE_MESSAGEABLE_CHANNEL, AutocompleteContext, ChannelType, DMGroup, File, InteractionContext, Member, Message, OptionType, User, slash_option

from discordbot import emoji
from discordbot.shared import channel_id, guild_id
from magic import card, card_price, database, fetcher, image_fetcher, oracle, rotation, seasons, whoosh_write
from magic.models import Card
from magic.whoosh_search import SearchResult, WhooshSearcher
from shared import configuration, dtutil
from shared import redis_wrapper as redis
from shared.lazy import lazy_property
from shared.settings import with_config_file

if TYPE_CHECKING:
    from discordbot.bot import Bot

DEFAULT_CARDS_SHOWN = 4
MAX_CARDS_SHOWN = 10
HELP_GROUPS: set[str] = set()

@lazy_property
def searcher() -> WhooshSearcher:
    try:
        return WhooshSearcher()
    except whoosh.index.EmptyIndexError:  # Whoosh hasn't been initialized yet!
        whoosh_write.reindex()
        return WhooshSearcher()

async def respond_to_card_names(ctx: 'MtgMessageContext') -> None:
    # Don't parse messages with Gatherer URLs because they use square brackets in the querystring.
    if 'gatherer.wizards.com' in ctx.message.content.lower():
        return
    compat = False and ctx.channel.type == ChannelType.GUILD_TEXT and await ctx.bot.get_user(268547439714238465) in ctx.channel.members  # see #7074
    queries = parse_queries(ctx.message.content, compat)
    if len(queries) > 0:
        try:
            await ctx.channel.trigger_typing()
        except Forbidden:
            return
        results = results_from_queries(queries)
        cards = []
        for query, i in zip(queries, results):
            (r, mode, preferred_printing) = i
            if r.has_match() and not r.is_ambiguous():
                cards.extend(cards_from_names_with_mode([r.get_best_match()], mode, preferred_printing, query))
            elif r.is_ambiguous():
                cards.extend(cards_from_names_with_mode(r.get_ambiguous_matches(), mode, preferred_printing, query))
        await ctx.post_cards(cards, ctx.author)

def parse_queries(content: str, scryfall_compatability_mode: bool) -> list[str]:
    to_scan = re.sub('`{1,3}[^`]*?`{1,3}', '', content, flags=re.DOTALL)  # Ignore angle brackets inside backticks. It's annoying in #code.
    if scryfall_compatability_mode:
        queries = re.findall(r'(?<!\[)\[([^\]]*)\](?!\])', to_scan)  # match [card] but not [[card]]
    else:
        queries = re.findall(r'\[?\[([^\]]*)\]\]?', to_scan)
    return [card.canonicalize(query) for query in queries if len(query) > 2]

def cards_from_names_with_mode(cards: Sequence[str | None], mode: str, preferred_printing: str | None = None, requested_name: str | None = None) -> list[Card]:
    return [copy_with_mode(oracle.load_card(c), mode, preferred_printing, requested_name) for c in cards if c is not None]

def copy_with_mode(oracle_card: Card, mode: str, preferred_printing: str | None = None, requested_name: str | None = None) -> Card:
    c = copy(oracle_card)
    c['mode'] = mode
    if requested_name:
        _requested_mode, name, _requested_printing = parse_mode(requested_name)
        alternate_name = oracle.matching_official_alternate_name(c, name)
        if alternate_name:
            c['display_name'] = alternate_name
            if preferred_printing is None:
                printing = oracle.preferred_printing_for_alternate_name(c, alternate_name)
                if printing is not None:
                    preferred_printing = str(printing.set_code)
                    c['preferred_printing_system_id'] = str(printing.system_id)
    c['preferred_printing'] = preferred_printing
    return c

def card_name_for_display(c: Card) -> str:
    display_name = c.get('display_name')
    if display_name and display_name != c.name:
        return f'{display_name} ({c.name})'
    return str(c.name)

def parse_mode(query: str) -> tuple[str, str, str | None]:
    mode = ''
    preferred_printing = None
    if query.startswith('$'):
        mode = '$'
        query = query[1:]
    if '|' in query and len(re.split(r'\|+', query)) == 2:
        query, preferred_printing = re.split(r'\|+', query)
        preferred_printing = preferred_printing.lower().strip()
    return mode, query, preferred_printing

def results_from_queries(queries: list[str]) -> list[tuple[SearchResult, str, str | None]]:
    all_results = []
    for query in queries:
        mode, query, preferred_printing = parse_mode(query)
        result = searcher().search(query)
        all_results.append((result, mode, preferred_printing))
    return all_results

def complex_search(query: str) -> list[Card]:
    if query == '':
        return []
    _num, cardnames, _results = fetcher.search_scryfall(query)
    cbn = oracle.cards_by_name()
    return [cbn[name] for name in cardnames if cbn.get(name) is not None]

def roughly_matches(s1: str, s2: str) -> bool:
    return simplify_string(s1).find(simplify_string(s2)) >= 0

def simplify_string(s: str) -> str:
    s = ''.join(s.split())
    return re.sub(r'[\W_]+', '', s).lower()

async def single_card_or_send_error(channel: TYPE_MESSAGEABLE_CHANNEL, args: str, author: Member, command: str) -> Card | None:
    if not args:
        await send(channel, f'{author.mention}: Please specify a card name.')
        return None
    result, mode, preferred_printing = results_from_queries([args])[0]
    if result.has_match() and not result.is_ambiguous():
        return cards_from_names_with_mode([result.get_best_match()], mode, preferred_printing, args)[0]
    if result.is_ambiguous():
        await send(channel, f'{author.mention}: Ambiguous name for {command}. Please use the slash command and choose one of its suggestions.')
    else:
        await send(channel, f'{author.mention}: No matches.')
    return None

async def single_card_text(client: Client, channel: TYPE_MESSAGEABLE_CHANNEL, args: str, author: Member, f: Callable[[Card], str], command: str, show_legality: bool = True) -> None:
    c = await single_card_or_send_error(channel, args, author, command)
    if c is not None:
        name = card_name_for_display(c)
        info_emoji = emoji.info_emoji(c, show_legality=show_legality)
        text = await emoji.replace_emoji(f(c), client)
        message = f'**{name}** {info_emoji} {text}'
        await send(channel, message)

async def post_nothing(channel: PrefixedContext | InteractionContext | TYPE_MESSAGEABLE_CHANNEL, replying_to: Member | User | None = None) -> None:
    if replying_to is not None:
        text = f'{replying_to.mention}: No matches.'
    else:
        text = 'No matches.'
    text += stale_card_information_warning()
    message = await send(channel, text)
    await message.add_reaction('❎')

def stale_card_information_warning() -> str:
    age = database.stale_card_information_age()
    if age is not None:
        return f'\nWARNING: card information is {dtutil.display_time(age.total_seconds(), 1)} old'
    return ''


async def send(channel: PrefixedContext | InteractionContext | TYPE_MESSAGEABLE_CHANNEL, content: str, file: File | None = None) -> Message:
    new_s = escape_underscores(content)
    return await channel.send(file=file, content=new_s)

async def send_image_with_retry(channel: PrefixedContext | InteractionContext | TYPE_MESSAGEABLE_CHANNEL, image_file: str, text: str = '') -> None:
    message = await send(channel, file=File(image_file), content=text)
    if message and message.attachments and message.attachments[0].size == 0:
        logging.warning('Message size is zero so resending')
        await message.delete()
        await send(channel, file=File(image_file), content=text)

async def single_card_text_internal(client: Client, requested_card: Card, legality_format: str) -> str:
    mana = await emoji.replace_emoji('|'.join(requested_card.mana_cost or []), client)
    mana = mana.replace('|', ' // ').removeprefix(' // ').removesuffix(' // ')  # Strip leading/trailing // for lands (See #9147)
    legal = ' — ' + emoji.info_emoji(requested_card, verbose=True, legality_format=legality_format)
    if requested_card.get('mode', None) == '$':
        text = f'{card_name_for_display(requested_card)} {legal} — {card_price.card_price_string(requested_card)}'
    else:
        text = f'{card_name_for_display(requested_card)} {mana} — {requested_card.type_line}{legal}'
    if requested_card.bugs:
        for bug in requested_card.bugs:
            text += '\n:lady_beetle:{rank} bug: {bug}'.format(bug=bug['description'], rank=bug['classification'])
            if bug['last_confirmed'] < (dtutil.now() - datetime.timedelta(days=60)):
                time_since_confirmed = (dtutil.now() - bug['last_confirmed']).total_seconds()
                text += f' (Last confirmed {dtutil.display_time(time_since_confirmed, 1)} ago.)'
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
def uniqify_cards(cards: list[Card]) -> list[Card]:
    # Remove multiple printings of the same card from the result set.
    results: dict[str, Card] = collections.OrderedDict()
    for c in cards:
        results[card.canonicalize(c.name)] = c
    return list(results.values())

def slash_card_option(param: str = 'card') -> Callable:
    """Predefined Slash command argument `card`"""

    def wrapper(func: Callable) -> Callable:
        return slash_option(
            name=param,
            description='Name of a Card',
            required=True,
            opt_type=OptionType.STRING,
            autocomplete=True,
        )(func)

    return wrapper

def make_choice(value: str, name: str | None = None) -> dict[str, int | float | str]:
    return {
        'name': (name or value)[:100],
        'value': value[:100],
    }

@global_autocomplete('card')
async def autocomplete_card(ctx: AutocompleteContext) -> None:
    query = ctx.kwargs.get('card')
    if not query:
        await ctx.send(choices=[])
        return
    results = searcher().search(query)
    choices = list(dict.fromkeys(results.get_all_matches()))
    formatted_choices = []
    for canonical_name in choices[:20]:
        c = oracle.load_card(canonical_name)
        alternate_name = oracle.matching_official_alternate_name(c, query, allow_prefix=True)
        if alternate_name:
            formatted_choices.append(make_choice(alternate_name, f'{alternate_name} — {canonical_name}'))
        else:
            formatted_choices.append(make_choice(canonical_name))
    await ctx.send(choices=formatted_choices)

class MtgMixin:
    async def send_image_with_retry(self: 'MtgContext', image_file: str, text: str = '') -> None:  # type: ignore
        message = await self.send(file=File(image_file), content=text)
        if message and message.attachments and message.attachments[0].size == 0:
            logging.warning('Message size is zero so resending')
            await message.delete()
            await self.send(file=File(image_file), content=text)

    async def single_card_text(self: 'MtgContext', c: Card, f: Callable, show_legality: bool = True) -> None:  # type: ignore
        if c is None:
            return

        not_pd = configuration.get_list('not_pd')
        if not self.channel:
            pass  # Not sure how we got here, but it happened
        elif str(self.channel.id) in not_pd:
            show_legality = False
        elif not isinstance(self.channel, (DM, DMGroup)) and str(self.channel.guild.id) in not_pd:
            show_legality = False

        name = card_name_for_display(c)
        info_emoji = emoji.info_emoji(c, show_legality=show_legality)
        text = await emoji.replace_emoji(f(c), self.bot)
        message = f'**{name}** {info_emoji} {text}{stale_card_information_warning()}'
        await self.send(message)

    async def post_cards(self: 'MtgContext', cards: list[Card], replying_to: User | Member | None = None, additional_text: str = '') -> None:  # type: ignore
        if len(cards) == 0:
            await post_nothing(self, replying_to)
            return

        with with_config_file(guild_id(self)), with_config_file(channel_id(self)):
            legality_format = configuration.legality_format.value
        not_pd = configuration.get_list('not_pd')
        if str(channel_id(self)) in not_pd or str(guild_id(self)) in not_pd:  # This needs to be migrated
            legality_format = 'Unknown'
        cards = uniqify_cards(cards)
        if rotation.in_rotation():
            cards = sorted(cards, key=lambda c: (not c.legal_in(seasons.current_season_name()), not redis.sismember('decksite:rotation:summary:legal', c.name), c.name))
        if len(cards) > MAX_CARDS_SHOWN:
            cards = cards[:DEFAULT_CARDS_SHOWN]
        if len(cards) == 1:
            text = await single_card_text_internal(self.bot, cards[0], legality_format)
        else:
            text = ' • '.join('{name} {legal} {price}'.format(name=card_name_for_display(card), legal=(emoji.info_emoji(card, legality_format=legality_format)), price=((card_price.card_price_string(card, True)) if card.get('mode', None) == '$' else '')).strip() for card in cards)
        if len(cards) > MAX_CARDS_SHOWN:
            image_file = None
        else:
            try:
                if isinstance(self, InteractionContext):
                    await self.defer()
            except Exception:
                pass
            image_file = await image_fetcher.download_image_async(cards)
        if image_file is None:
            text += '\n\n'
            if len(cards) == 1:
                text += await emoji.replace_emoji(cards[0].oracle_text, self.bot)
            else:
                text += 'No image available.'
        text += additional_text
        text += stale_card_information_warning()
        if image_file is None:
            await send(self, text)
        else:
            await send_image_with_retry(self, image_file, text)

    async def post_nothing(self: 'MtgContext') -> None:  # type: ignore
        await post_nothing(self)


@attr.define(init=False)
class MtgInteractionContext(SlashContext, MtgMixin):
    @property
    def bot(self) -> 'Bot':
        return cast('Bot', self.client)

@attr.define(init=False)
class MtgMessageContext(PrefixedContext, MtgMixin):
    pass


MtgContext = MtgMessageContext | MtgInteractionContext
